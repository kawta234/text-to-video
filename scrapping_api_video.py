import requests
import os
import pandas as pd
from PIL import Image
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from keybert import KeyBERT
from moviepy.editor import VideoFileClip
import cv2
import torch
from collections import Counter
import io
import uuid
import boto3
from pathlib import Path
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from nltk.corpus import wordnet
import numpy as np




def stem_words(word,porter):
    stemmed_word = porter.stem(word) 
    return stemmed_word

def find_video_for_term(term, processed_terms, processed_video_paths, metadata):
    print(term)

    topic_found = False
    video_found = False
    video_name = None
    new_metadata = metadata[~metadata['path_datalake'].isin(processed_video_paths)]
    url_datalake_path = None 

    if term not in processed_terms:
        for idx, meta_row in new_metadata.iterrows():
            main_topic_stemmed = meta_row['main_topic']  # Assuming main_topic is a list of stemmed words
            # Check for exact match
            main_topic_list = eval(main_topic_stemmed)
            if term in main_topic_list :  
                video_name = meta_row['name']
                url_datalake_path = meta_row['path_datalake'] 
                if url_datalake_path is not None:
                    processed_terms.add(term)
                    topic_found = True
                    video_found = True
                break

    return topic_found, video_found, video_name, url_datalake_path


def get_video_duration(video_url):
    try:
        clip = VideoFileClip(video_url)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        print(f"Error occurred while getting video duration: {str(e)}")
        return 0
    
def is_video_readable(url):
    try:
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            cap.release()
            return True
        else:
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def lexical_similarity(word1, word2):
    synsets1 = wordnet.synsets(word1)
    synsets2 = wordnet.synsets(word2)

    max_similarity = 0

    for synset1 in synsets1:
        for synset2 in synsets2:
            similarity = synset1.wup_similarity(synset2)  # Wu-Palmer Similarity
            if similarity is not None and similarity > max_similarity:
                max_similarity = similarity

    return max_similarity

def search_pixabay_video(query, api_key,processed_video_paths, per_page=3, safe_search=True):
    
    safe_search_param = 'true' if safe_search else 'false'
    processed_image_paths = [
        path.split('.jpg')[0].replace("datalake_media/image-", "") + '.jpg' 
        if '.jpg' in path else path.replace("datalake_media/image-", "") 
        for path in processed_image_paths
    ]
    
    print("processed_image_paths to search in pixabay:", processed_image_paths)
    url = f'https://pixabay.com/api/?key={api_key}&q={query}&per_page={per_page}&safesearch={safe_search_param}'
    
    # ADD TIMEOUT HERE
    try:
        response = requests.get(url, timeout=10)  # 10 second timeout
    except requests.Timeout:
        print(f"Timeout occurred for query: {query}")
        return []
    except requests.RequestException as e:
        print(f"Request error for query {query}: {e}")
        return []
    
    if response.status_code == 200:
        hits = response.json()['hits']
      
        if hits:
            videos = []
            for resp in hits:
                print("tags",resp['tags'])
                url_resp = resp['videos']['large']['url']
                filename = url_resp.split('/')[-1].split('?')[0]
                keywords = resp['tags'].split(', ')
                topic_name = keywords[0]
                score = lexical_similarity(query, topic_name)
                print("Score between:", topic_name, " and ", query, " is ", score)
                if score ==0:
                    videos=[]
                    break
                if score >= 0.4:
                    if filename not in processed_video_paths:
                        videos.append(resp)
                    else:
                        print("filename ",filename, 'is already used')
                elif score <= 0.4:
                    current_page = 1
                    while len(videos) < 1:
                        current_page += 1
                        new_url = f'https://pixabay.com/api/videos/?key={api_key}&q={query}&per_page={per_page}&safesearch={safe_search_param}&page={current_page}'
                        new_response = requests.get(new_url)
                        if new_response.status_code == 200:
                            new_hits = new_response.json()['hits']
                            if not new_hits:
                                break  
                            for new_resp in new_hits:
                                new_preview_url = new_resp['videos']['large']['url']
                                new_filename = new_preview_url.split('/')[-1].split('?')[0]
                                print(new_filename)
                                new_keywords = new_resp['tags'].split(', ')
                                new_topic_name = new_keywords[0]
                                new_score = lexical_similarity(query, new_topic_name)
                                print("Score between:", new_topic_name, " and ", query, " is ", new_score)
                                if new_score >= 0.4:
                                    if new_filename not in processed_video_paths:
                                        videos.append(new_resp)
                                    else:
                                        print(new_filename,'file already in metadata')
                        else:
                            break
            return videos
        else:
            print(f"No videos found for query: {query}")
            return []
    else:
        print(f"Error: Failed to retrieve videos for query: {query}")
        return []


def download_media(media):
    """
    Downloads video files and saves them to a local folder.

    Args:
        media (dict): A dictionary containing video information, including the URL.

    Returns:
        tuple: The filename and the local path of the saved file.
    """
    local_video_folder = r"C:\Users\jakjo\Desktop\TTV\epigrowth\API_US388\images"

    url = media['videos']['large']['url']
    filename = url.split('/')[-1].split('?')[0]
    print("filename is:", filename)
    
    if not filename:
        print("Filepath is None")
        return None, None
    
    # Check if the video is readable
    video_opened = is_video_readable(url)
    if video_opened:
        # Generate a unique filename to avoid overwriting
        unique_filename = f"video-{filename}-{str(uuid.uuid4())}.mp4"
        local_path = os.path.join(local_video_folder, unique_filename)
        
        # Download the video content and save it locally
        with open(local_path, 'wb') as video_file:
            video_file.write(requests.get(url).content)
        
        print(f"Video saved locally at: {local_path}")
        return filename, local_path
    else:
        print("Video is not readable.")
        return filename, None

def create_video_dataframe(videos, keywords, term):
    data = []
    for video in videos:
        if video is not None:
            name,path_datalake = download_media(video)
            if name is not None and path_datalake is not None:  
                url = video['videos']['large']['url']
                data.append([name, keywords, url, 'video', term,path_datalake,0,0,'useful'])
    columns = ['name', 'keywords', 'url', 'type', 'term','path_datalake','count_usage','count_edit','media_state']
    return pd.DataFrame(data, columns=columns)

def stem_words_(words):
    porter = PorterStemmer()
    tokens = word_tokenize(words)
    stemmed_words = [porter.stem(word) for word in tokens]

    return stemmed_words

def find_main_terms(row, n=3):
    combined_keywords = row['topic_name']+[row['term']]+ row['keywords'] + row['keywords_description'] 
    stemmed_keywords = stem_words_(' '.join(combined_keywords))
    keyword_freq = pd.Series(stemmed_keywords).value_counts()
    print(keyword_freq)
    top_terms = keyword_freq.head(n).index.tolist()

    return top_terms

def search_videos_for_dataframe_pixabay(term, api_key,metadata):
    video_dataframes = []
    used_terms = set()
    if term not in used_terms:
        videos = search_pixabay_video(term, api_key)
        if videos:
            for video in videos:
                keywords = video['tags'].split(', ')
                df_video = create_video_dataframe([video], keywords, term)
                video_paths = df_video['url']
                #print("video_paths:", video_paths)
                print("video path:",video_paths)
                preds_string, description_keywords = generate_video_description(video_paths)
                df_video['description'] = preds_string
                df_video['keywords_description'] = description_keywords
                video_dataframes.append(df_video)
                
            used_terms.add(term)

    videos_df = pd.concat(video_dataframes, ignore_index=True)
    metadata_file = 'new_metadata_mixkit_unsplash_pixabay.xlsx' #should change    
    merged_metadata = pd.concat([videos_df, metadata], ignore_index=True)
    merged_metadata['source'] = 'pixabay'
    merged_metadata.to_excel(metadata_file, index=False)
    
    return videos_df


def search_video_for_dataframe_pixabay_video(terms, api_key,processed_video_paths):
    metadata=pd.read_excel(r"C:\Users\jakjo\Desktop\TTV\epigrowth\API_US388\new_metadata_mixkit_unsplash_pixabay-4.xlsx")

    video_dataframes = []
    used_terms = set()
    for term in terms:
        if term not in used_terms:
            videos = search_pixabay_video(term, api_key,processed_video_paths)
            if videos:
                for video in videos:
                    keywords = video['tags'].split(', ')
                    keywords=str(keywords)
                    df_video = create_video_dataframe([video], keywords, term)
                    video_urls = df_video['url']
                    #preds_string, description_keywords = generate_video_description(video_urls)
                    df_video['description'] = ""
                    df_video['keywords_description'] = str([])
                    df_video['term']= df_video['term'].astype(str)
                    df_video['topic_name'] = df_video['name'].str.split('-').str[0].apply(lambda x: [x])
                    df_video['keywords_description'] = df_video['keywords_description'].apply(lambda x: eval(x))
                    df_video['keywords'] = df_video['keywords'].apply(lambda x: eval(x))
                    # df_video['main_topic'] = df_video.apply(find_main_terms, axis=1)
                    df_video['source'] = 'pixabay'

                    video_dataframes.append(df_video)

                used_terms.add(term)
                break
        
    if video_dataframes!= []:
        videos_df = pd.concat(video_dataframes, ignore_index=True)
        merged_metadata = pd.concat([videos_df, metadata], ignore_index=True)

        video_path=videos_df['path_datalake'][0]
        video_path=[video_path]
        merged_metadata.loc[merged_metadata['path_datalake'] == video_path, 'count_usage'] += 1
        # with io.BytesIO() as buffer:
        #     merged_metadata.to_excel(buffer, index=False)
        #     buffer.seek(0)
        #     data_bytes = buffer.read() 
        # put_image_in_s3(data_bytes,"soulchain-dev1-output-video", "new_metadata_mixkit_unsplash_pixabay.xlsx")

    else:
        video_path=["datalake_media/default_video.mp4"]
            
    return  video_path 
    


from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from keybert import KeyBERT


def generate_video_description(video_urls):
    model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    feature_extractor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")

    captions_all_videos = []
    keywords_all_videos = []

    print(video_urls)

    for video_url in video_urls:
        video_capture = cv2.VideoCapture(video_url)
        
        if not video_capture.isOpened():
            print(f"Error: Unable to open video URL '{video_url}'.")
            continue

        ret, frame = video_capture.read()
        if not ret:
            print(f"Error: No frames found in video '{video_url}'.")
            video_capture.release()
            continue

        pixel_values = feature_extractor(images=frame, return_tensors="pt").pixel_values
        output_ids = model.generate(pixel_values, max_length=50, num_beams=1, early_stopping=True)
        caption = tokenizer.decode(output_ids[0], skip_special_tokens=True)

        key_model = KeyBERT()
        keywords_with_scores = key_model.extract_keywords(caption)
        description_keywords = [keyword for keyword, score in keywords_with_scores]
        description_keywords_str = str(description_keywords)

        captions_all_videos.append(caption)
        keywords_all_videos.append(description_keywords_str)

        video_capture.release()

    return captions_all_videos, keywords_all_videos