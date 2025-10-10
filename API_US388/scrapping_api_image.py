import requests
import os
import pandas as pd
from PIL import Image
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from keybert import KeyBERT
from datalake import upload_file_to_s3, generate_download_url, download_file_from_s3, put_image_in_s3,read_metadata_from_s3
import io
from io import BytesIO
import uuid
import boto3
from pathlib import Path
from nltk.stem import PorterStemmer
import gensim.downloader as api
from gensim.models import KeyedVectors
from nltk.corpus import wordnet
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer



def find_image_for_topic(term, metadata):
    url_datalake_paths = []
    metadata = metadata.dropna(subset=['keywords'])

    for idx, meta_row in metadata.iterrows():
        main_topic_stemmed = meta_row['keywords']

        if term in main_topic_stemmed:
            url_datalake_paths.append(meta_row['path_datalake'])
        if len(url_datalake_paths) == 30:
            break

    return url_datalake_paths

def preprocess_text(text):
    stop_words = set(stopwords.words('english'))
    word_tokens = word_tokenize(text.lower())
    filtered_words = [w for w in word_tokens if w.isalnum() and w not in stop_words]
    return filtered_words

def calculate_similarity(topics, keywords):
    vectorizer = CountVectorizer().fit_transform([topics, keywords])
    vectors = vectorizer.toarray()
    cosine_sim = cosine_similarity(vectors)
    return cosine_sim[0][1]

def find_image_for_term_test(terms, processed_terms, processed_media_paths, metadata):
    topic_found = False
    image_found = False
    image_name = None
    metadata = metadata.dropna(subset=['keywords_description'])
    new_metadata = metadata[~metadata['path_datalake'].isin(processed_media_paths)]
    url_datalake_path = None 
    preprocessed_topics = ' '.join(terms)

    best_score = 0
    best_image_index = -1

    for index, row in new_metadata.iterrows():
        human_keywords = ' '.join(eval(row['keywords']))
        ai_keywords = ' '.join(eval(row['keywords_description']))
        
        human_similarity = calculate_similarity(preprocessed_topics, human_keywords)
        ai_similarity = calculate_similarity(preprocessed_topics, ai_keywords)
        
        avg_similarity = (human_similarity + ai_similarity) / 2
        
        if avg_similarity > best_score:
            best_score = avg_similarity
            best_image_index = index

    if best_image_index != -1:
        best_image_metadata = new_metadata.iloc[best_image_index]

    return best_image_metadata['path_datalake']


def stem_words(word,porter):
    stemmed_word = porter.stem(word) 
    return stemmed_word

def find_image_for_term(term, processed_terms, processed_image_paths, metadata, image_folder):

    topic_found = False
    image_found = False
    image_name = None
    metadata = metadata.dropna(subset=['keywords_description'])
    new_metadata = metadata[~metadata['path_datalake'].isin(processed_image_paths)]
    url_datalake_path = None 

    #if term not in processed_terms:
    for idx, meta_row in new_metadata.iterrows():
        main_topic_stemmed = meta_row['main_topic']  # Assuming main_topic is a list of stemmed words
        # Check for exact match
        main_topic_list = eval(main_topic_stemmed)
        #if term in main_topic_list or term in meta_row["keywords_description"] or term in meta_row["keywords"]: 
        if term in main_topic_list:  
 
            image_name = meta_row['name']
            url_datalake_path = meta_row['path_datalake'] 
            if url_datalake_path is not None:
                #processed_terms.add(term)
                topic_found = True
                image_found = True
            break

    return topic_found, image_found, image_name, url_datalake_path

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

def search_pixabay_images(query, api_key,processed_image_paths, per_page=3, safe_search=True):
    safe_search_param = 'true' if safe_search else 'false'
    processed_image_paths=[path.split('.jpg')[0].replace("datalake_media/image-", "") + '.jpg' if '.jpg' in path else path.replace("datalake_media/image-", "") for path in processed_image_paths]
    print("processed_image_paths to search in pixabay:",processed_image_paths)
    url = f'https://pixabay.com/api/?key={api_key}&q={query}&per_page={per_page}&safesearch={safe_search_param}'
    response = requests.get(url)
    if response.status_code == 200:
        hits = response.json()['hits']
        if hits:
            images = []
            for resp in hits:
                preview_url = resp['previewURL']
                filename = preview_url.split('/')[-1]
                print(filename)
                topic_name = preview_url.split('/')[-1].split('-')[0]
                score = lexical_similarity(query, topic_name)
                print("Score between:", topic_name, " and ", query, " is ", score)
                if score == 0:
                    images=[]
                    break
                if score >= 0.4:
                    if filename not in processed_image_paths:
                        images.append(resp)
                    else:
                        print("filename ",filename, 'is already used')
                elif score <= 0.4:
                    current_page = 1
                    while len(images) < 1:
                        current_page += 1
                        new_url = f'https://pixabay.com/api/?key={api_key}&q={query}&per_page={per_page}&safesearch={safe_search_param}&page={current_page}'
                        new_response = requests.get(new_url)
                        if new_response.status_code == 200:
                            new_hits = new_response.json()['hits']
                            if not new_hits:
                                break  
                            for new_resp in new_hits:
                                new_preview_url = new_resp['previewURL']
                                new_filename = new_preview_url.split('/')[-1]
                                print(new_filename)
                                new_topic_name = new_preview_url.split('/')[-1].split('-')[0]

                                new_score = lexical_similarity(query, new_topic_name)
                                print("Score between:", new_topic_name, " and ", query, " is ", new_score)
                                if new_score >= 0.4:
                                    if new_filename not in processed_image_paths:
                                        images.append(new_resp)
                                    else:
                                        print(new_filename,'file already in metadata')
                        else:
                            break

            print("done scrapping")

            return images
        else:
            print(f"No images found for query: {query}")
            return []
    else:
        print(f"Error: Failed to retrieve images for query: {query}")
        return []
    

def google_image_search(api_key, search_engine_id, query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': api_key,
        'cx': search_engine_id,
        'q': query,
        'searchType': 'image',
        'num': 1
    }
    response = requests.get(url, params=params)
    response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    return response.json()

def download_image(image):
    preview_url = image['previewURL']
    print(preview_url)
    
    large_url = image['largeImageURL']
    filename = preview_url.split('/')[-1]
    if filename=='':

        # api_key = 'AIzaSyDIj3PxevGpBnr8MCuxX4z089o4yNQevrU'
        # search_engine_id = 'c6684e252cbae47c2'
        # large_url = google_image_search(api_key, search_engine_id, query)
        s3_key=None
        print("filepath is None")
    else:
        output_bucket = "soulchain-dev1-output-video"
        s3_key = f"datalake_media/image-{filename}-{str(uuid.uuid4())}"
        put_image_in_s3(requests.get(large_url).content,output_bucket,s3_key)
    return filename, s3_key

def stem_words_(words):
    porter = PorterStemmer()
    tokens = word_tokenize(words)
    stemmed_words = [porter.stem(word) for word in tokens]

    return stemmed_words

def find_main_terms(row, n=3):
    combined_keywords = row['topic_name']+[row['term']]+ row['keywords'] + row['keywords_description'] 
    stemmed_keywords = stem_words_(' '.join(combined_keywords))
    keyword_freq = pd.Series(stemmed_keywords).value_counts()
    top_terms = keyword_freq.head(n).index.tolist()
    return top_terms

def create_image_dataframe(images, keywords, term):
    data = []
    for image in images:
        if image is not None:
            name ,path_datalake= download_image(image)
            if name is not None:
                url = image['previewURL']
                data.append([name, keywords, url, 'image', term, path_datalake,0,0,'useful'])
    columns = ['name', 'keywords', 'url', 'type', 'term','path_datalake','count_usage','count_edit','media_state']
    print("dataframe created")
    return pd.DataFrame(data, columns=columns)


def predict_step(image_urls):
    model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    feature_extractor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")

    max_length = 16
    num_beams = 4
    gen_kwargs = {"max_length": max_length, "num_beams": num_beams}

    images = []
    for image_url in image_urls:
        response = requests.get(image_url)
        i_image = Image.open(BytesIO(response.content))
        if i_image.mode != "RGB":
            i_image = i_image.convert(mode="RGB")
        images.append(i_image)

    pixel_values = feature_extractor(images=images, return_tensors="pt").pixel_values

    output_ids = model.generate(pixel_values, **gen_kwargs)

    preds = tokenizer.batch_decode(output_ids, skip_special_tokens=True)
    preds = [pred.strip() for pred in preds]
    description = " ".join(preds)

    key_model = KeyBERT()
    keywords_with_scores = key_model.extract_keywords(description)
    description_keywords = [keyword for keyword, score in keywords_with_scores]
    description_keywords_str = str(description_keywords)
    
    print("Description done")
    return description, description_keywords_str


def search_images_for_dataframe_pixabay(term, api_key,image_folder,metadata):
    image_dataframes = []
    used_terms = set()
    if term not in used_terms:
        images = search_pixabay_images(term, api_key,3)
        if images:
            for image in images:
                keywords = image['tags'].split(', ')
                df_image = create_image_dataframe([image], keywords, term)
                image_urls = df_image['url']
                preds_string, description_keywords = predict_step(image_urls)
                df_image['description'] = preds_string
                df_image['keywords_description'] = description_keywords
                image_dataframes.append(df_image)
            used_terms.add(term)
        

    images_df = pd.concat(image_dataframes, ignore_index=True)
    metadata_file = 'new_new_metadata_mixkit_unsplash_pixabay.xlsx'
    merged_metadata = pd.concat([images_df, metadata], ignore_index=True)
    merged_metadata['source'] = 'pixabay'
    merged_metadata.to_excel(metadata_file, index=False)
    
    return images_df

def search_images_for_dataframe_pixabay_video(terms, api_key,processed_image_paths,l=1):
    metadata=read_metadata_from_s3("soulchain-dev1-output-video", "new_new_metadata_mixkit_unsplash_pixabay.xlsx")
    image_dataframes = []
    used_terms = set()
    for term in terms:
        if term not in used_terms:
            images = search_pixabay_images(term, api_key,processed_image_paths)
            if images:
                for image in images:
                    keywords = image['tags'].split(', ')
                    keywords=str(keywords)
                    df_image = create_image_dataframe([image], keywords, term)
                    image_urls = df_image['url']
                    #preds_string, description_keywords = predict_step(image_urls)
                    df_image['description'] = ""
                    df_image['keywords_description'] = str([])
                    df_image['term']= df_image['term'].astype(str)
                    df_image['topic_name'] = df_image['name'].str.split('-').str[0].apply(lambda x: [x])
                    df_image['keywords_description'] = df_image['keywords_description'].apply(lambda x: eval(x))
                    df_image['keywords'] = df_image['keywords'].apply(lambda x: eval(x))
                    #df_image['main_topic'] = df_image.apply(find_main_terms, axis=1)
                    df_image['source'] = 'pixabay'
                    image_dataframes.append(df_image)

                used_terms.add(term)
                break

    print("image_dataframes: ",image_dataframes)
        
    if image_dataframes != []:
        images_df = pd.concat(image_dataframes, ignore_index=True)
        # merged_metadata = pd.concat([images_df, metadata], ignore_index=True)
        image_path=images_df['path_datalake'][0]
        image_path=[image_path]
        # merged_metadata.loc[merged_metadata['path_datalake'] == image_path, 'count_usage'] += 1
        print(image_path)

        # with io.BytesIO() as buffer:
        #         merged_metadata.to_excel(buffer, index=False)
        #         buffer.seek(0)
        #         data_bytes = buffer.read() 
        # put_image_in_s3(data_bytes,"soulchain-dev1-output-video", "new_metadata_mixkit_unsplash_pixabay.xlsx")

    else :
        image_path=["datalake_media/default_image.jpg"]
    return  image_path
    
