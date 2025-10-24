import requests
import os
import pandas as pd
from PIL import Image
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from keybert import KeyBERT
import io
from io import BytesIO
import uuid
from pathlib import Path
from nltk.stem import PorterStemmer
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

def search_pixabay_images(query, api_key, processed_image_paths, per_page=3, safe_search=True):
    safe_search_param = 'true' if safe_search else 'false'
    processed_image_paths = [path.split('.jpg')[0].replace("datalake_media/image-", "") + '.jpg' if '.jpg' in path else path.replace("datalake_media/image-", "") for path in processed_image_paths]
    print("processed_image_paths to search in pixabay:", processed_image_paths)
    
    url = f'https://pixabay.com/api/?key={api_key}&q={query}&per_page={per_page}&safesearch={safe_search_param}'
    response = requests.get(url)
    
    if response.status_code == 200:
        hits = response.json()['hits']
        if hits:
            images = []
            query_terms = [term.lower() for term in query.split()]  # Split query into individual terms
            print(f"Searching for images with ALL terms: {query_terms}")
            
            for resp in hits:
                preview_url = resp['previewURL']
                filename = preview_url.split('/')[-1]
                print(f"\nChecking: {filename}")
                
                # Get image tags
                tags = resp.get('tags', '').lower()
                tags_list = [tag.strip() for tag in tags.split(',')]
                print(f"Image tags: {tags_list}")
                
                # Check if ALL query terms are present in tags
                terms_found = []
                for query_term in query_terms:
                    # Check exact match in tags
                    if query_term in tags:
                        terms_found.append(query_term)
                        print(f"  ✓ Found '{query_term}' in tags")
                    else:
                        # Check lexical similarity with each tag
                        best_tag_score = 0
                        best_tag = None
                        for tag in tags_list:
                            score = lexical_similarity(query_term, tag)
                            if score > best_tag_score:
                                best_tag_score = score
                                best_tag = tag
                        
                        if best_tag_score >= 0.4:
                            terms_found.append(query_term)
                            print(f"  ✓ Found '{query_term}' similar to tag '{best_tag}' (score: {best_tag_score:.2f})")
                        else:
                            print(f"  ✗ '{query_term}' not found (best match: '{best_tag}' with score {best_tag_score:.2f})")
                
                # Calculate match percentage
                match_percentage = len(terms_found) / len(query_terms) if query_terms else 0
                print(f"Match: {len(terms_found)}/{len(query_terms)} terms ({match_percentage:.0%})")
                
                # Accept image if ALL terms are found (100% match)
                if match_percentage == 1.0:
                    if filename not in processed_image_paths:
                        images.append(resp)
                        print(f"✓ ACCEPTED - All terms matched!")
                    else:
                        print(f"✗ Already used: {filename}")
                else:
                    print(f"✗ REJECTED - Not all terms matched")
                
                # Stop if we found enough images
                if len(images) >= per_page:
                    break
            
            # If no images found with all terms, try paginating
            if not images:
                print(f"\n→ No images found on page 1 with all terms. Trying more pages...")
                current_page = 1
                max_pages = 5  # Limit pagination to avoid too many API calls
                
                while len(images) < 1 and current_page < max_pages:
                    current_page += 1
                    print(f"\n→ Trying page {current_page}...")
                    
                    new_url = f'https://pixabay.com/api/?key={api_key}&q={query}&per_page={per_page}&safesearch={safe_search_param}&page={current_page}'
                    new_response = requests.get(new_url)
                    
                    if new_response.status_code == 200:
                        new_hits = new_response.json()['hits']
                        if not new_hits:
                            print("No more results available")
                            break
                        
                        for new_resp in new_hits:
                            new_preview_url = new_resp['previewURL']
                            new_filename = new_preview_url.split('/')[-1]
                            print(f"\nChecking: {new_filename}")
                            
                            # Get image tags
                            new_tags = new_resp.get('tags', '').lower()
                            new_tags_list = [tag.strip() for tag in new_tags.split(',')]
                            print(f"Image tags: {new_tags_list}")
                            
                            # Check if ALL query terms are present
                            new_terms_found = []
                            for query_term in query_terms:
                                if query_term in new_tags:
                                    new_terms_found.append(query_term)
                                    print(f"  ✓ Found '{query_term}' in tags")
                                else:
                                    best_tag_score = 0
                                    best_tag = None
                                    for tag in new_tags_list:
                                        score = lexical_similarity(query_term, tag)
                                        if score > best_tag_score:
                                            best_tag_score = score
                                            best_tag = tag
                                    
                                    if best_tag_score >= 0.4:
                                        new_terms_found.append(query_term)
                                        print(f"  ✓ Found '{query_term}' similar to tag '{best_tag}' (score: {best_tag_score:.2f})")
                                    else:
                                        print(f"  ✗ '{query_term}' not found")
                            
                            new_match_percentage = len(new_terms_found) / len(query_terms) if query_terms else 0
                            print(f"Match: {len(new_terms_found)}/{len(query_terms)} terms ({new_match_percentage:.0%})")
                            
                            if new_match_percentage == 1.0:
                                if new_filename not in processed_image_paths:
                                    images.append(new_resp)
                                    print(f"✓ ACCEPTED - All terms matched!")
                                    break
                                else:
                                    print(f"✗ Already used: {new_filename}")
                            else:
                                print(f"✗ REJECTED - Not all terms matched")
                        
                        if images:
                            break
                    else:
                        print("API request failed")
                        break
            
            print("\ndone scrapping")
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

# def download_image(image):
#     preview_url = image['previewURL']
#     print(preview_url)
    
#     large_url = image['largeImageURL']
#     filename = preview_url.split('/')[-1]
#     if filename=='':

#         # api_key = 'AIzaSyDIj3PxevGpBnr8MCuxX4z089o4yNQevrU'
#         # search_engine_id = 'c6684e252cbae47c2'
#         # large_url = google_image_search(api_key, search_engine_id, query)
#         s3_key=None
#         print("filepath is None")
#     else:
#         output_bucket = "soulchain-dev1-output-video"
#         s3_key = f"datalake_media/image-{filename}-{str(uuid.uuid4())}"
#         put_image_in_s3(requests.get(large_url).content,output_bucket,s3_key)
#     return filename, s3_key

def download_image(image):
    preview_url = image['previewURL']
    print(preview_url)
    
    large_url = image['largeImageURL']
    filename = preview_url.split('/')[-1]
    
    if filename == '':
        # If filename is empty, handle the error or provide an alternative
        print("Filename is empty, unable to save the image.")
        s3_key = None
    else:
        # Specify the local directory path
        local_directory = r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\images"
        
        # Ensure the directory exists
        if not os.path.exists(local_directory):
            os.makedirs(local_directory)
        
        # Generate a unique file path
        unique_filename = f"image-{filename}-{str(uuid.uuid4())}.jpg"
        file_path = os.path.join(local_directory, unique_filename)
        
        # Fetch the image content and save it locally
        response = requests.get(large_url)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"Image saved to {file_path}")
        else:
            print(f"Failed to download image from {large_url}")
    
    return filename, file_path


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

import random

import logging
logger = logging.getLogger(__name__)

def search_images_for_dataframe_pixabay_video(terms, api_key, processed_image_paths, l=1):
   
    """
    Search for images using combined terms instead of individual terms.
    
    Args:
        terms: List of terms to search (will be combined into one query)
        api_key: Pixabay API key
        processed_image_paths: List of already used image paths
        l: Number of images to collect
    
    Returns:
        List of image paths
    """
    logger.info(f"\n--- SEARCHING FOR {l} IMAGES ---")
    logger.info(f"Search terms: {terms}")
    logger.info(f"Already processed images: {processed_image_paths}")
    
    image_dataframes = []
    collected_images = 0
    
    # Combine all terms into a single search query
    combined_query = ' '.join(terms)
    logger.info(f"Combined search query: '{combined_query}'")
    
    # Search with the combined query
    logger.info(f"  Searching Pixabay for combined query: '{combined_query}'")
    
    images = search_pixabay_images(combined_query, api_key, processed_image_paths)
    
    if images:
        logger.info(f"  ✓ Found {len(images)} images for '{combined_query}'")
        
        images_needed = min(l - collected_images, len(images))
        
        for idx, image in enumerate(images[:images_needed]):
            # LOG IMAGE DETAILS
            logger.info(f"    Image {idx+1}: ID={image.get('id')}, URL={image.get('largeImageURL')}")
            logger.info(f"    Tags: {image.get('tags', 'N/A')}")
            
            keywords = image['tags'].split(', ')
            keywords = str(keywords)
            df_image = create_image_dataframe([image], keywords, combined_query)
            
            # LOG PATH
            if 'path_datalake' in df_image.columns:
                img_path = df_image['path_datalake'].iloc[0]
                logger.info(f"    ✓ Selected path: {img_path}")
            
            image_urls = df_image['url']
            df_image['description'] = ""
            df_image['keywords_description'] = str([])
            df_image['term'] = df_image['term'].astype(str)
            df_image['topic_name'] = df_image['name'].str.split('-').str[0].apply(lambda x: [x])
            df_image['keywords_description'] = df_image['keywords_description'].apply(lambda x: eval(x))
            df_image['keywords'] = df_image['keywords'].apply(lambda x: eval(x))
            df_image['source'] = 'pixabay'
            image_dataframes.append(df_image)
            
            collected_images += 1
            
            if collected_images >= l:
                break
    else:
        logger.warning(f"  ✗ No images found for combined query: '{combined_query}'")
        
        # Fallback: try searching with individual terms if combined query fails
        logger.info(f"  → Trying fallback: searching individual terms")
        terms_shuffled = list(terms)
        random.shuffle(terms_shuffled)
        
        for term in terms_shuffled:
            if collected_images >= l:
                break
                
            logger.info(f"  Fallback search for term: '{term}'")
            images = search_pixabay_images(term, api_key, processed_image_paths)
            
            if images:
                logger.info(f"  ✓ Found {len(images)} images for '{term}'")
                
                images_needed = min(l - collected_images, len(images))
                
                for idx, image in enumerate(images[:images_needed]):
                    logger.info(f"    Image {idx+1}: ID={image.get('id')}, URL={image.get('largeImageURL')}")
                    logger.info(f"    Tags: {image.get('tags', 'N/A')}")
                    
                    keywords = image['tags'].split(', ')
                    keywords = str(keywords)
                    df_image = create_image_dataframe([image], keywords, term)
                    
                    if 'path_datalake' in df_image.columns:
                        img_path = df_image['path_datalake'].iloc[0]
                        logger.info(f"    ✓ Selected path: {img_path}")
                    
                    image_urls = df_image['url']
                    df_image['description'] = ""
                    df_image['keywords_description'] = str([])
                    df_image['term'] = df_image['term'].astype(str)
                    df_image['topic_name'] = df_image['name'].str.split('-').str[0].apply(lambda x: [x])
                    df_image['keywords_description'] = df_image['keywords_description'].apply(lambda x: eval(x))
                    df_image['keywords'] = df_image['keywords'].apply(lambda x: eval(x))
                    df_image['source'] = 'pixabay'
                    image_dataframes.append(df_image)
                    
                    collected_images += 1
                    
                    if collected_images >= l:
                        break

    if image_dataframes:
        images_df = pd.concat(image_dataframes, ignore_index=True)
        
        available_paths = images_df['path_datalake'].tolist()
        
        # Filter out already used images
        available_paths = [
            path for path in available_paths 
            if path not in processed_image_paths
        ]
        
        image_path = available_paths[:l] if len(available_paths) >= l else available_paths
        
        while len(image_path) < l:
            logger.warning("  ⚠ Not enough images, using default")
            image_path.append("datalake_media/default_image.jpg")
        
        logger.info(f"✓ FINAL SELECTION ({len(image_path)} images):")
        for idx, path in enumerate(image_path, 1):
            logger.info(f"  {idx}. {path}")
    else:
        image_path = ["datalake_media/default_image.jpg"] * l
        logger.warning(f"✗ NO IMAGES FOUND - Using {l} default images")
    
    return image_path