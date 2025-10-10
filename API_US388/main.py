from topic import find_topics
from audio import audio_generation_tts
from video import make_video_from_video_test
from image import make_video_from_images_test,generate_final_video,find_media_from_images_test
from update import change_media,update_text_in_json,update_media_in_json,def_change_translation,delete_scene,replace_audio,change_media_path,change_media_url_path
from datalake import read_metadata_from_s3
from scrapping_api_image import find_image_for_term, search_images_for_dataframe_pixabay_video,find_image_for_topic,find_image_for_term_test
from scrapping_api_video import find_video_for_term, search_videos_for_dataframe_pixabay,search_video_for_dataframe_pixabay_video
from mix import make_video_parts_mixed
from upload import create_image_dataframe_pixabay,read_metadata_from_s3,create_image_dataframe_google,create_image_dataframe_pexels
from add_scene import add_video_part
import os
import json
from botocore.exceptions import ClientError
import requests
import uuid
import elevenlabs
from flask import Flask, request
from flask.json import jsonify
import pandas as pd
import numpy as np
import nltk
import boto3
from io import BytesIO
from moviepy.editor import ImageClip
import os
import spacy.cli
from flask import Flask
from flask_cors import CORS
from manual_generation import split_text,generate_manual_audio,read_txt_from_s3



# Set TOKENIZERS_PARALLELISM environment variable
os.environ["TOKENIZERS_PARALLELISM"] = "false"


#nltk.download('punkt')
#nltk.download('stopwords')
#spacy.cli.download("en_core_web_md")
#nltk.download('averaged_perceptron_tagger')
#nltk.download('wordnet')



app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:4200"}})
# CORS(app, resources={
#     r"/api/*": {
#         "origins": 
#             "http://192.168.7.59", 
#             "http://localhost:4200" # Replace with your allowed IP
#         ]
#     }
# })

@app.route('/make_video_parts', methods=['POST'])
def make_video():
    try:
        data = request.get_json()
        user_id=data.get('user_id')
        language = data.get('language')
        video_type = data.get('video_type')  
        pixabay_api_key = "41475535-6d87f1c0e99d7a58bc22bfbda"
        eleven_api="e3a9b4546de3b481827f7480c0af5c74"
        final_video_width=data.get('final_video_width')
        final_video_height=data.get('final_video_height')
        sub=data.get("sub")
        animation = data.get("animation")

        text = data.get('text')

        video_id= f"video_{user_id}_{str(uuid.uuid4())}"
        metadata=read_metadata_from_s3("soulchain-dev1-output-video", "new_new_metadata_mixkit_unsplash_pixabay.xlsx")
        
        if final_video_width>final_video_height:
            size="horizontal"
        if final_video_width<final_video_height: 
            size="vertical"
        if final_video_width==final_video_height:
            size="square"

        metadata = metadata[metadata["size"] == size]


        df = find_topics(text)
        print(df.columns)
        print(df['terms'])
        
        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")

        audio_generation_tts(df,video_id)

        if video_type == 'image':
            topic_clips = make_video_from_images_test(s3,language,df,user_id,video_id, pixabay_api_key, metadata,final_video_width, final_video_height, sub,animation)
            return jsonify({'video_info':topic_clips})
        
        elif video_type == 'video':
            topic_clips = make_video_from_video_test(s3,language,df,user_id,video_id, pixabay_api_key, metadata,final_video_width, final_video_height,sub)
            return jsonify({'video_info': topic_clips})
        
        elif video_type=='mix':
            topic_clips = make_video_parts_mixed(s3,language,df,user_id,video_id, pixabay_api_key, metadata,final_video_width, final_video_height,sub, animation)
            return jsonify({'video_info': topic_clips})

        return jsonify({"message": "Video creation successful"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/make_final_video', methods=['POST'])
def make_final_video():
    try:
        data = request.get_json()
        video_id= data.get('video_id')
        background_music_file=data.get('background_music_file')
        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")

        url=generate_final_video(s3,video_id,background_music_file)
        return jsonify({'Final video generated':url})
        
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_video_parts', methods=['POST'])

def update_video_parts():
    try:
        
        data = request.get_json()
        final_video_width=data.get('final_video_width')
        final_video_height=data.get('final_video_height')
        media_keys=data.get('media_keys')
        new_media_paths=data.get('new_media_paths')
        video_id=data.get("video_id")
        video_type=data.get("video_type")

        if new_media_paths and isinstance(new_media_paths, list):

            updated_media_paths = []
            
            for sublist in new_media_paths:
                if isinstance(sublist, list):
                    updated_sublist = []
                    for path in sublist:
                        if path.startswith('datalake_media') :
                            if isinstance(path, str):
                                start_index = path.find("datalake_media")
                                
                                if start_index != -1:
                                    end_index = path.find("?", start_index)
                                    
                                    if end_index != -1:
                                        updated_sublist.append(path[start_index:end_index])
                                    else:
                                        updated_sublist.append(path[start_index:])
                        else: 
                            updated_sublist.append(path)
                    updated_media_paths.append(updated_sublist)
                else:
                    updated_media_paths.append(sublist)
            
            new_media_paths = updated_media_paths
        else:
            new_media_paths = []
                    

        new_texts=data.get("new_texts")
        text_keys=data.get('text_keys')
        audio_keys=data.get('audio_keys')
        position =data.get("position")
        fontsize= data.get("fontsize")
        font_name= data.get("font_name")
        color= data.get("color")
        bg_color= data.get("bg_color")
        sub=data.get("sub")
        animation = data.get("animation")


        print("bg_color",bg_color)

        final_keys = text_keys + audio_keys + media_keys
        final_keys = list(set(final_keys))

        # if position!= 'bottom' or fontsize!=34 or font_name!="Arial-Bold" or color != "white" or bg_color!= "black":
        #     final_keys= "all"

       
        video_id= data.get('video_id')
        
        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")
        metadata=read_metadata_from_s3("soulchain-dev1-output-video", "new_metadata_mixkit_unsplash_pixabay.xlsx") 
          
        # for path in new_media_paths:
        #     metadata.loc[metadata["path_datalake"] == path, "tendency_score"] += 1

        update_text_in_json(s3,video_id, text_keys,new_texts)
        print("update_text_in_json done")
        
        update_media_in_json(s3,video_id,metadata, media_keys, new_media_paths) 

        print("update_media_in_json done")

        all_parts_keys=change_media_path(s3,sub,final_keys,video_id, final_video_width, final_video_height,animation,position,fontsize,font_name,color,bg_color)       

        return jsonify({"message": all_parts_keys}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/update_video_parts_font', methods=['POST'])

def update_video_parts_font():
    try:
        
        data = request.get_json()
        final_video_width=data.get('final_video_width')
        final_video_height=data.get('final_video_height')
        position =data.get("position")
        fontsize= data.get("fontsize")
        font_name= data.get("font_name")
        color= data.get("color")
        bg_color= data.get("bg_color")
        video_id= data.get('video_id')
        sub=data.get("sub")
        animation = data.get("animation")

        
        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")

        all_parts_keys=change_media_path(s3,sub,"all",video_id, final_video_width, final_video_height,animation,position,fontsize,font_name,color,bg_color)       

        return jsonify({"message": all_parts_keys}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update_translation', methods=['POST'])
def update_translation():
    try:
        
        data = request.get_json()
        language = data.get('language')
        video_id= data.get('video_id')

        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")

        translated_part=def_change_translation(s3,video_id, language)

        return jsonify({"message": translated_part}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/update_scenes', methods=['POST'])
def update_scenes():
    try:
        
        data = request.get_json()
        final_video_width=data.get('final_video_width')
        final_video_height=data.get('final_video_height')
        position =data.get("position")
        fontsize= data.get("fontsize")
        font_name= data.get("font_name")
        color= data.get("color")
        bg_color= data.get("bg_color")
        video_id= data.get('video_id')
        sub =data.get('sub')
        animation = data.get("animation")

        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")

        all_parts_keys=change_media_url_path(s3,sub,"all",video_id, final_video_width, final_video_height,animation,position,fontsize,font_name,color,bg_color)       

        return jsonify({"message": all_parts_keys}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/delete_scenes', methods=['POST'])
def delete_scenes():
    try:
        
        data = request.get_json()
        index = data.get('index')
        video_id= data.get('video_id')

        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")

        video_parts=delete_scene(s3, video_id, index)
       

        return jsonify({"message": video_parts}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/add_scene', methods=['POST'])

def add_scene():
    try:
        
        data = request.get_json()
        text = data.get('text')
        video_id= data.get('video_id')
        media_type=data.get("media_type")
        lang=data.get("language")
        user_id=data.get("user_id")
        final_video_width=data.get("final_video_width")
        final_video_height=data.get("final_video_height")
        sub=data.get("sub")
        animation = data.get("animation")

        position =data.get("position")
        fontsize= data.get("fontsize")
        font_name= data.get("font_name")
        color= data.get("color")
        bg_color= data.get("bg_color")
        api_key= "41475535-6d87f1c0e99d7a58bc22bfbda"

        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")
        metadata=read_metadata_from_s3("soulchain-dev1-output-video", "new_new_metadata_mixkit_unsplash_pixabay.xlsx")
        video_parts=add_video_part(s3, video_id, metadata, text, media_type, lang, user_id, api_key, final_video_width, final_video_height, sub,animation,position,fontsize,font_name,color,bg_color)
        return jsonify({"message": video_parts}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/replace_audio', methods=['POST'])
def replace_audios():
    try:
        
        data = request.get_json()
        audio_key = data.get('audio_key')
        video_id= data.get('video_id')
        base64_audio=data.get('base64_audio')

        replace_audio(video_id,audio_key,base64_audio)
    
        return jsonify({"message": "audio replaced"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/find_media_by_topic', methods=['POST']) 
def find_media_by_topic():
    try:
        data=request.get_json()
        topic=data.get('topic')
        media_type=data.get('media_type')
        # final_video_width=data.get('final_video_width')
        # final_video_height=data.get('final_video_height')
        metadata=read_metadata_from_s3("soulchain-dev1-output-video", "new_metadata_mixkit_unsplash_pixabay.xlsx")
        metadata = metadata[metadata["type"] == media_type]
        metadata = metadata[metadata["media_state"] == 'useful']

        # if final_video_width>final_video_height:
        #     size="horizontal"
        # if final_video_width<final_video_height: 
        #     size="vertical"
        # if final_video_width==final_video_height:
        #     size="square"
        # metadata = metadata[metadata["size"] == size]
        
        list_media=find_image_for_topic(topic,metadata)

        return list_media 

    except Exception as e:
        return jsonify({"error": str(e)}), 500 
    

@app.route('/upload_media_by_topic_pixabay', methods=['POST']) 
def upload_media_by_topic_pixabay():
    try:
        data=request.get_json()
        topic=data.get('topic')
        media_type=data.get('media_type')
        media=data.get("media")
        s3_path=create_image_dataframe_pixabay(media, topic,media_type)
        return jsonify({"message": s3_path}), 200  

    except Exception as e:
        return jsonify({"error": str(e)}), 500 
    


@app.route('/upload_media_by_topic_pexels', methods=['POST']) 
def upload_media_by_topic_pexels():
    try:
        data=request.get_json()
        topic=data.get('topic')
        media_type=data.get('media_type')
        media=data.get("media")
        s3_path=create_image_dataframe_pexels(media, topic,media_type)
        return jsonify({"message": s3_path}), 200  

    except Exception as e:
        return jsonify({"error": str(e)}), 500 

@app.route('/upload_media_by_topic_google', methods=['POST']) 
def upload_media_by_topic_google():
    try:
        data=request.get_json()
        topic=data.get('topic')
        media_type=data.get('media_type')
        url=data.get("url")
        s3_path=create_image_dataframe_google(url, topic,media_type)
        return jsonify({"message": s3_path}), 200  

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/get_json_file', methods=['POST']) 
def get_json_file():

    data = request.get_json()
    video_id=data.get("video_id")
    s3 = boto3.client('s3', aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")


    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')
        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise  

    video = next((v for v in data if v["video_id"] == video_id), None)

    return jsonify({'Video info': video})


@app.route('/get_videos_by_user_id', methods=['POST']) 
def get_videos_by_user_id():

    data = request.get_json()
    user_id=data.get("user_id")
    s3 = boto3.client('s3', aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")


    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        existing_data_all = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data_all = []
        else:
            raise

        
    existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]

    return jsonify({'Video info': existing_data})

@app.route('/split_text', methods=['POST']) 
def split_text_function():
    data = request.get_json()
    user_id=data.get("user_id")
    text=data.get("text")
    video_id= f"video_{user_id}_{str(uuid.uuid4())}"
    lang=data.get("language")
    s3 = boto3.client('s3', aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="B8BLl4w+34+SdyAyzSTXJuYaqGo3ZqF0IvtYKDkB")
    df= find_topics(text)
    file_name = "example.txt"
    file_content = " "
    with open(file_name, 'w') as file:
        file.write(file_content)

    s3.upload_file(file_name, 'soulchain-dev1-output-video', f"text_info/{user_id}/example.txt")

    video_info = split_text(s3,lang,df,user_id,video_id)
    return video_info

@app.route('/find_topics', methods=['POST']) 
def find_topics_by_text():
    data = request.get_json()
    user_id=data.get("user_id")
    text=data.get("text")
    s3 = boto3.client('s3', aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="B8BLl4w+34+SdyAyzSTXJuYaqGo3ZqF0IvtYKDkB")

    file_name = "example.txt"
    file_content = "We are extracting topics from the text you inserted"
    with open(file_name, 'w') as file:
        file.write(file_content)

    s3.upload_file(file_name, 'soulchain-dev1-output-video', f"text_info/{user_id}/example.txt")
    df= find_topics(text)
    json_str = df.to_json(orient='records')

    video_id= f"video_{user_id}_{str(uuid.uuid4())}"

    response = {
        "topics": json.loads(json_str),
        "video_id": video_id
    }

    return jsonify(response)


@app.route('/create_video_id', methods=['POST']) 
def create_video_id():
    try:
        data = request.get_json()
        user_id=data.get('user_id')
        video_id= f"video_{user_id}_{str(uuid.uuid4())}"

        return jsonify({'video_id':video_id})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/find_medias', methods=['POST']) 
def find_medias():
    try:
        data = request.get_json()
        output=data.get("data")
        df = output['topics']
        video_id = output['video_id']
        df= pd.DataFrame(df)
        user_id=data.get('user_id')
        # video_id=data.get("video_id")
        language = data.get('language')
        video_type = data.get('video_type')  
        pixabay_api_key = "41475535-6d87f1c0e99d7a58bc22bfbda"
        # video_id= f"video_{user_id}_{str(uuid.uuid4())}"

        print("data", data)

        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")
        metadata=read_metadata_from_s3("soulchain-dev1-output-video", "new_new_metadata_mixkit_unsplash_pixabay.xlsx")

        if video_type=="image":
            topic_clips=find_media_from_images_test(s3,language,df,user_id,video_id,pixabay_api_key, metadata,indx=1)
            return jsonify({'video_info':topic_clips})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/create_audios', methods=['POST']) 
def create_audios():
    try:
        data = request.get_json()
        output=data.get("data")
        df = output['topics']
        df= pd.DataFrame(df)
        video_id = output['video_id'] 
        user_id=data.get('user_id')
        # video_id=data.get("video_id")
        # video_id= f"video_{user_id}_{str(uuid.uuid4())}"
        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="B8BLl4w+34+SdyAyzSTXJuYaqGo3ZqF0IvtYKDkB")

        url_tts = "http://127.0.0.1:5013/tts/tts"
        for index, row in df.iterrows():
            file_name = "example.txt"
            file_content = f'Generating audio for part {index+1}'
            with open(file_name, 'w') as file:
                file.write(file_content)

            s3.upload_file(file_name, 'soulchain-dev1-output-video', f"text_info/{user_id}/example.txt")
            data = {
                "text": row["sentence"],
                "video_id":video_id,
                "sentence_id":row["sentence_part_id"],
                "chemin":"voices/test_sounny.mp3"

            }
            requests.post(url_tts, json=data)
        return jsonify({"video_id": video_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
     


@app.route('/generate_audios', methods=['POST']) 
def generate_audios():
    try:
        data = request.get_json()
        video_id=data.get("video_id")
        video_parts = data.get("video_parts")
        extracted_data = []
        for part in video_parts:
            text = part['text']
            key = part['key']-1
            extracted_data.append({
                'text': text,
                'key': key
            })

        url_tts = "http://127.0.0.1:5013/tts/tts"
        for row in extracted_data:
            data = {
                "text": row["text"],
                "video_id":video_id,
                "sentence_id":row["key"],
                "chemin":"voices/test_sounny.mp3"

            }
            requests.post(url_tts, json=data)
        return jsonify({"Audios generated for ": video_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/create_scenes', methods=['POST'])
def create_scenes():
    try:
        data = request.get_json() 
        final_video_width=data.get('final_video_width')
        final_video_height=data.get('final_video_height')
        position =data.get("position")
        fontsize= data.get("fontsize")
        font_name= data.get("font_name")
        new_media_paths=data.get("new_media_paths")
        color= data.get("color")
        bg_color= data.get("bg_color")
        video_id= data.get('video_id')
        sub =data.get('sub')
        animation = data.get("animation")

        metadata=read_metadata_from_s3("soulchain-dev1-output-video", "new_metadata_mixkit_unsplash_pixabay.xlsx")

        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")
        #print("generating audio")
        #generate_manual_audio(s3, video_id)
        print("creating videos")
        update_media_in_json(s3,video_id,metadata, "all", new_media_paths)
        print("change media")
        all_parts_keys=change_media(s3,sub,"all",video_id, final_video_width, final_video_height,animation,"bottom",34,"Arial","white","black")       

        return jsonify({"message": all_parts_keys}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/read_txt', methods=['POST'])
def read_txt():
    try:
        data = request.get_json()
        user_id=data.get("user_id")
        bucket_name = 'soulchain-dev1-output-video'
        file_key = f"text_info/{user_id}/example.txt"
        file_content = read_txt_from_s3(bucket_name, file_key)
        return jsonify({"message": file_content}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500   


@app.route('/get_history', methods=['POST'])
def get_history():

    try:
        data = request.get_json()
        user_id=data.get("user_id")
        session = boto3.Session(region_name='eu-west-1')
        s3 = session.client('s3',aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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")
        
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        existing_data_all = json.loads(response['Body'].read())
            
        existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]

        return jsonify({"video_info": existing_data}), 200



    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data_all = []
        else:
            raise


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
