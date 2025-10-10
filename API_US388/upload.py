import boto3
import requests
import uuid
import pandas as pd
from io import BytesIO
import io


def read_metadata_from_s3(bucket_name, file_key):
    s3 = boto3.client('s3', aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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",region_name='eu-west-1')
    obj = s3.get_object(Bucket=bucket_name, Key=file_key)
    return pd.read_excel(BytesIO(obj['Body'].read()))

def put_image_in_s3(media,bucket_name,object_key):
    s3 = boto3.client('s3', aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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",region_name='eu-west-1')

    try:
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=media)
        print("Media uploaded successfully to S3")
    except Exception as e:
        print(f"An error occurred: {e}")


def download_media_pixabay(media, media_type):

    if media_type == 'image':
        preview_url = media['previewURL']
        url = media.get('largeImageURL', media.get('previewURL'))
        filename = preview_url.split('/')[-1]

    else:
        url = media.get('videos', {}).get('large', {}).get('url')
        filename = url.split('/')[-1].split('?')[0]
    if not url:
        print("URL is invalid or missing")
        return None, None
    
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to download media. HTTP Status Code: {response.status_code}")
        return None, None,None
    

     
    s3_key = f"datalake_media/{media_type}-{filename}-{str(uuid.uuid4())}"
    put_image_in_s3(response.content, 'soulchain-dev1-output-video', s3_key)

    return filename,s3_key,url


def create_image_dataframe_pixabay(media, term, media_type):

    metadata=read_metadata_from_s3("soulchain-dev1-output-video", "metadata_mixkit_unsplash_pixabay.xlsx")    
    data = []
    
    if media is not None:
        name ,path_datalake,url= download_media_pixabay(media, media_type)
        keywords = media['tags'].split(', ')
        keywords=str(keywords)

        if name is not None:
            data.append([name, keywords, url, media_type, term, path_datalake," ",[],'pixabay',[],[term],0,0,'useful'])
    columns = ['name', 'keywords', 'url', 'type', 'term','path_datalake','description','keywords_description'
               ,'source','topic_name','main_topic','count_usage','count_edit','media_state']
    print("dataframe created")

    media_df=pd.DataFrame(data, columns=columns)

    merged_metadata = pd.concat([media_df, metadata], ignore_index=True)

    with io.BytesIO() as buffer:
        merged_metadata.to_excel(buffer, index=False)
        buffer.seek(0)
        data_bytes = buffer.read()

    
    put_image_in_s3(data_bytes,"soulchain-dev1-output-video", "metadata_mixkit_unsplash_pixabay.xlsx")

    return path_datalake



def download_media_google(url,term, media_type):

    name=f"{term}_cat_google"
    
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to download media. HTTP Status Code: {response.status_code}")
        return None, None
    
     
    s3_key = f"datalake_media/{media_type}-{term}-{str(uuid.uuid4())}"
    put_image_in_s3(response.content, 'soulchain-dev1-output-video', s3_key)

    return name,s3_key


def create_image_dataframe_google(url,term,media_type):
    metadata=read_metadata_from_s3("soulchain-dev1-output-video", "metadata_mixkit_unsplash_pixabay.xlsx")    

    data = []
    
    if not pd.isnull(url):
        name, path_datalake = download_media_google(url,term, media_type)
        
        data.append([name, [], url, media_type, term, path_datalake," ",[],'google',[],[term],0,0,'useful'])
            
    columns = ['name', 'keywords', 'url', 'type', 'term','path_datalake','description','keywords_description'
               ,'source','topic_name','main_topic','count_usage','count_edit','media_state']
    
    media_df=pd.DataFrame(data, columns=columns)

    merged_metadata = pd.concat([media_df, metadata], ignore_index=True)

    with io.BytesIO() as buffer:
        merged_metadata.to_excel(buffer, index=False)
        buffer.seek(0)
        data_bytes = buffer.read()
    
    put_image_in_s3(data_bytes,"soulchain-dev1-output-video", "metadata_mixkit_unsplash_pixabay.xlsx")

    return path_datalake


def download_media_pexels(media,term, media_type):

    url = media['src']['large']
    id = media['id']
    name=f"{media_type}_{id}_{term}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to download media. HTTP Status Code: {response.status_code}")
        return None, None
    
     
    s3_key = f"datalake_media/{media_type}-{term}-{str(uuid.uuid4())}"
    put_image_in_s3(response.content, 'soulchain-dev1-output-video', s3_key)

    return name,s3_key,url


def create_image_dataframe_pexels(media,term,media_type):
    metadata=read_metadata_from_s3("soulchain-dev1-output-video", "metadata_mixkit_unsplash_pixabay.xlsx")    

    data = []
    
    if not pd.isnull(media):
        name, path_datalake,url = download_media_google(media,term, media_type)
        
        data.append([name, [], url, media_type, term, path_datalake," ",[],'pexels',[],[term],0,0,'useful'])
            
    columns = ['name', 'keywords', 'url', 'type', 'term','path_datalake','description','keywords_description'
               ,'source','topic_name','main_topic','count_usage','count_edit','media_state']
    
    media_df=pd.DataFrame(data, columns=columns)

    merged_metadata = pd.concat([media_df, metadata], ignore_index=True)

    with io.BytesIO() as buffer:
        merged_metadata.to_excel(buffer, index=False)
        buffer.seek(0)
        data_bytes = buffer.read()
    
    put_image_in_s3(data_bytes,"soulchain-dev1-output-video", "metadata_mixkit_unsplash_pixabay.xlsx")