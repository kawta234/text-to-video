from io import BytesIO
import io
import numpy as np
import tempfile
import cv2
import uuid
import boto3
from botocore.exceptions import ClientError
import os
import json
from datetime import datetime, timedelta
import pandas as pd
from datalake import put_image_in_s3
from nltk.stem import PorterStemmer
from PIL import Image
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, CompositeVideoClip
from scrapping_api_image import search_images_for_dataframe_pixabay_video, find_image_for_term 
from text import create_text_clip
import requests
from text_to_media import find_media_best
from langdetect import detect
from text import def_translation




# def get_argos_model(source, target):
#     lang = f'{source} -> {target}'
#     source_lang = [model for model in translate.get_installed_languages() if lang in map(repr, model.translations_from)]
#     target_lang = [model for model in translate.get_installed_languages() if lang in map(repr, model.translations_to)]
    
#     return source_lang[0].get_translation(target_lang[0])


def replace_default_image(image_path_list, processed_image_paths):
    for i in range(len(image_path_list)):
        if image_path_list[i] == "datalake_media/default_image.jpg":
            if i > 0:
                image_path_list[i] = image_path_list[i - 1]
            else:
                image_path_list[i] = processed_image_paths[-1]

    print("done replacing")
    return image_path_list

def image_used_in_30_days(image_path, date_now , existing_data):
    image_used=False 
    for entry in existing_data:
        for part in entry['video_parts']:
            if part['image_key'] == image_path:
                date_created = entry['date_created']
                break
    date_created = datetime.fromisoformat(date_created)
    if timedelta(days=-30)<=date_now - date_created <= timedelta(days=30):
        image_used=True 

    return image_used

def resize_and_fit(image, target_width, target_height, background_color=(0, 0, 0)):
    
    image.thumbnail((target_width, target_height), Image.ANTIALIAS)
    
    new_image = Image.new("RGB", (target_width, target_height), background_color)
    
    x_offset = (target_width - image.width) // 2
    y_offset = (target_height - image.height) // 2
    
    new_image.paste(image, (x_offset, y_offset))
    
    return new_image

def make_video_from_images_test(s3,lang,df,user_id,video_id,api_key, metadata,final_video_width, final_video_height,sub,animation,position='bottom',fontsize=34,font_name="Arial-Bold",color='white',bg_color='black',indx=1):
    

    add_scene=indx
    metadata_image = metadata[metadata["type"] == 'image']
    metadata_image = metadata_image[metadata_image["media_state"] == 'useful']

    topic_clips = []
    video_parts = []

    processed_terms = set()  

    ### retrieving the json file  

    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        existing_data_all = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data_all = []
        else:
            raise

    ### filtering user_id data
        
    existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]

    ### to be used in function find_image_for_term()
    processed_image_paths = []
    for entry in existing_data:
        processed_image_paths.extend([part['media_key'] for part in entry['video_parts']])
    print("processed_image_paths: ",processed_image_paths)
    

    for index, row in df.iterrows():
        sentence = row['sentence']
        topic_found = False
        image_found = False

        l=1

        # if 50<=len(sentence)<=100:
        #     l=2
        # if len(sentence)>100:
        #     l=3

        topics =row['terms']

        topic_found, image_found,image_path_list = find_media_best(topics, processed_image_paths, metadata_image,l)  
        image_path_list = replace_default_image(image_path_list,processed_image_paths)

        print(image_path_list)
                    

        if topic_found and image_found:
            print("image_found and topic_found")
            processed_image_paths=processed_image_paths+image_path_list
            

        if not topic_found or not image_found:
            image_path_list = search_images_for_dataframe_pixabay_video(row['terms'], api_key,[],l)
            print(image_path_list)
            image_path_list = replace_default_image(image_path_list,processed_image_paths)

            processed_image_paths=processed_image_paths+image_path_list

            print(image_path_list)
    
        # print("length of list of media:", len(image_path_list))
        try:
            response_audio = s3.get_object(Bucket='soulchain-dev1-output-video', Key=f"generated_videos/{video_id}/audio{indx}")
            audio_data = response_audio['Body'].read()
        except Exception as e:
            
            print("Error reading audio from S3:", e)

        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(audio_data)
            temp_file.seek(0)  
            
            audio = AudioFileClip(temp_file.name)

            
        image_clips=[]

        
        print("path lists before ietrating", image_path_list)
        
        for image_path in image_path_list:

            image_duration=audio.duration/len(image_path_list)

            try:
                response_image = s3.get_object(Bucket='soulchain-dev1-output-video', Key=image_path)
                image_data = response_image['Body'].read()
            except Exception as e:
                print("Error reading image from S3:", e)
                image_data=None

            image_stream = BytesIO(image_data)

            image = Image.open(image_stream)
            image = Image.open(image_stream).convert("RGB")
            image_np = np.array(image)

            image_clip = ImageClip(image_np, duration=(image_duration))

            image_clip = image_clip.resize((final_video_width, final_video_height))
            

            if animation=="True":
                image_clip = image_clip.resize(lambda t: (final_video_width * (1 + t/10), final_video_height * (1 + t/10)))
                image_clip = image_clip.set_position(lambda t: ('center', t * 10 + 50))
                target_width, target_height = final_video_width, final_video_height
                image_clip = image_clip.resize(lambda t: (
                    int(target_width * (1 + t / 20)),
                    int(target_height * (1 + t / 20))
                ))

            image_clips.append(image_clip)

            

        image_clip=concatenate_videoclips(image_clips, method="compose")
        image_clip = image_clip.set_audio(audio)
        
        subtitles = None
        
        if sub == "True":
            text_clip,subtitles = create_text_clip(lang,sentence, image_clip, audio.duration,position,fontsize,font_name,color,bg_color)
            print("subtitles",subtitles)
            text_clip = text_clip.set_position(position).margin(bottom=10)

            final_clip = CompositeVideoClip([image_clip, text_clip])
        else: 
            final_clip=image_clip
            print("No subtitles")

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_output_file:
            temp_output_file_path = temp_output_file.name
            final_clip.write_videofile(temp_output_file_path, fps=24,audio_codec='aac')

            try:
                key=f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4"
                s3.upload_file(temp_output_file_path, 'soulchain-dev1-output-video', f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4")
                print("Successfully uploaded the final video to S3.")
                topic_clips.append(key)
                if len(image_path_list)==1:
                    types=["image"]
                if len(image_path_list)==2:
                    types=["image","image"]
                if len(image_path_list)==3:
                    types=["image","image","image"]
                
                video_parts.append({
                    'key':indx,
                    'duration':audio.duration,
                    'media_key': image_path_list,
                    'audio_key': f"generated_videos/{video_id}/audio{indx}",
                    'text':sentence,
                    'subtitles':subtitles,
                    'video_part_key': key,
                    'media_type':types
                })

            except Exception as e:
                print("Error uploading final video to S3:", e)
        indx += 1 

    date_created = datetime.now().isoformat() 
    output_data = {
    'video_id': video_id,
    'user_id': user_id,
    'date_created':date_created,
    'video_key':f"generated_videos/{video_id}/final_video.mp4",
    'video_type':'image',
    'video_parts': video_parts
    }

    existing_data_all.append(output_data)

    json_data = json.dumps(existing_data_all)
        
    if add_scene == 1:
        s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=json_data)


    return output_data


def generate_final_video(s3, video_id, background_music_file):
    with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_audio_file:
        s3.download_file("soulchain-dev1-output-video", f"background_music/{background_music_file}", temp_audio_file.name)
        background_music = AudioFileClip(temp_audio_file.name)
        background_music = background_music.volumex(0.2)
        
        bucket = "soulchain-dev1-output-video"
        key = "video_info.json"
        response = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(response["Body"].read().decode("utf-8"))
        
        topic_clips = [
            part["video_part_key"] for video in data if video["video_id"] == video_id
            for part in video["video_parts"]
        ]
        
        clips = []
        for key in topic_clips:
            obj = s3.get_object(Bucket='soulchain-dev1-output-video', Key=key)
            video_buffer = io.BytesIO(obj['Body'].read())
            video_buffer.seek(0)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video_file:
                temp_video_file.write(video_buffer.read())
                temp_video_file.seek(0)
                clips.append(VideoFileClip(temp_video_file.name))
        
        final_video = concatenate_videoclips(clips, method="compose")
        
        background_music = background_music.subclip(0, final_video.duration)
        final_video = final_video.set_audio(CompositeAudioClip([final_video.audio, background_music]))
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as final_video_file:
            final_video.write_videofile(final_video_file.name, audio_codec='aac')
            final_video_file.seek(0)
            
            # Upload final video to S3
            with open(final_video_file.name, "rb") as f:
                s3.upload_fileobj(f, 'soulchain-dev1-output-video', f"generated_videos/{video_id}/final_video.mp4")
        
        # Clean up resources
        for clip in clips:
            clip.close()
    
    return f"generated_videos/{video_id}/final_video.mp4"



def find_media_from_images_test(s3,lang,df,user_id,video_id,api_key, metadata,indx=1):
    

    add_scene=indx
    metadata_image = metadata[metadata["type"] == 'image']
    metadata_image = metadata_image[metadata_image["media_state"] == 'useful']

    topic_clips = []
    video_parts = []

    processed_terms = set()  

    ### retrieving the json file  

    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        existing_data_all = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data_all = []
        else:
            raise

    ### filtering user_id data
        
    existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]

    ### to be used in function find_image_for_term()
    processed_image_paths = []
    for entry in existing_data:
        processed_image_paths.extend([part['media_key'] for part in entry['video_parts']])
    print("processed_image_paths: ",processed_image_paths)
    

    for index, row in df.iterrows():

        file_name = "example.txt"
        file_content = f'Finding image that matches the topics in part {indx}'
        with open(file_name, 'w') as file:
            file.write(file_content)

        s3.upload_file(file_name, 'soulchain-dev1-output-video', f"text_info/{user_id}/example.txt")
        sentence = row['sentence']
        topic_found = False
        image_found = False

        l=1

        if 50<=len(sentence)<=100:
            l=2
        if len(sentence)>100:
            l=3

        topics =row['terms']

        topic_found, image_found,image_path_list = find_media_best(topics, processed_image_paths, metadata_image,l)
        image_path_list=replace_default_image(image_path_list,processed_image_paths)
 
        print(image_path_list)
                    

        if topic_found and image_found:
            print("image_found and topic_found")
            # processed_image_paths=processed_image_paths+image_path_list
            

        if not topic_found or not image_found:
            image_path_list = search_images_for_dataframe_pixabay_video(row['terms'], api_key,[],l)
            image_path_list=replace_default_image(image_path_list,processed_image_paths)

            # processed_image_paths=processed_image_paths+image_path_list
            
    
            print("length of list of media:", len(image_path_list))
        try:
            response_audio = s3.get_object(Bucket='soulchain-dev1-output-video', Key=f"generated_videos/{video_id}/audio{indx}")
            audio_data = response_audio['Body'].read()
        except Exception as e:
            
            print("Error reading audio from S3:", e)

        try:
            key=f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4"
            print("Successfully uploaded the final video to S3.")
            topic_clips.append(key)
            if len(image_path_list)==1:
                types=["image"]
            if len(image_path_list)==2:
                types=["image","image"]
            if len(image_path_list)==3:
                types=["image","image","image"]

            subtitles=def_translation(sentence,lang)
            
            video_parts.append({
                'key':indx,
                'duration':0,
                'media_key': image_path_list,
                'audio_key': f"generated_videos/{video_id}/audio{indx}",
                'text':sentence,
                'subtitles':subtitles,
                'video_part_key': key,
                'media_type':types
            })

        except Exception as e:
            print("Error uploading final video to S3:", e)
        indx += 1 

    date_created = datetime.now().isoformat() 
    output_data = {
    'video_id': video_id,
    'user_id': user_id,
    'date_created':date_created,
    'video_key':f"generated_videos/{video_id}/final_video.mp4",
    'video_type':'image',
    'video_parts': video_parts
    }

    existing_data_all.append(output_data)

    json_data = json.dumps(existing_data_all)
        
    if add_scene == 1:
        s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=json_data)

    file_name = "example.txt"
    file_content = ""
    with open(file_name, 'w') as file:
        file.write(file_content)

    s3.upload_file(file_name, 'soulchain-dev1-output-video', f"text_info/{user_id}/example.txt")


    return output_data