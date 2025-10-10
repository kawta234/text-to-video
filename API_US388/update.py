import json
from botocore.exceptions import ClientError
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip,concatenate_videoclips
import tempfile
from io import BytesIO
from PIL import Image
import numpy as np
import requests
import uuid
import os
from datalake import put_image_in_s3
from text import create_text_updated_clip,def_translation
from langdetect import detect
from text import get_argos
import base64
import tempfile



def delete_scene(s3, video_id, scene_index):
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')
        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("No video_info.json file found.")
            return
        else:
            raise

    video = next((v for v in data if v["video_id"] == video_id), None)

    if video:
        video['video_parts'] = [part for part in video['video_parts'] if part['key'] != scene_index]
    else:
        print(f"No video found with video_id: {video_id}")
        return

    try:
        updated_data = json.dumps(data)
        s3.put_object(Bucket='soulchain-dev1-output-video', Key='video_info.json', Body=updated_data)
        print("JSON file successfully updated.")
    except Exception as e:
        print(f"Error while saving the JSON file: {e}")

    return video


def def_change_translation(s3,video_id, lang):
    translated_part=[]
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')
        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise  

    video = next((v for v in data if v["video_id"] == video_id), None)
    all_keys = []
    if video and "video_parts" in video:
        all_keys = [part['key'] for part in video['video_parts']]

    if video:
        for key in all_keys:
            part = next((p for p in video["video_parts"] if p["key"] == key), None)
            if part:
                part["subtitles"] = def_translation(part["text"],lang)
                translated_part.append(part["subtitles"])
    try:
        data = json.dumps(data)
        s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=data)
        print("JSON file successfully updated.")
    except Exception as e:
        print(f"Error while saving the JSON file: {e}")
    
    return translated_part


def download_new_media(media, media_type):

    if media_type == 'image':
        preview_url = media['previewURL']
        url = media.get('largeImageURL', media.get('previewURL'))
        filename = preview_url.split('/')[-1]

    else:
        url = media.get('videos', {}).get('large', {}).get('url')
        filename = url.split('/')[-1].split('?')[0]
    if not url:
        return None, None
    
    response = requests.get(url)
    if response.status_code != 200:
        return None, None
     
    s3_key = f"datalake_media/{media_type}-{filename}-{str(uuid.uuid4())}"
    put_image_in_s3(response.content, 'soulchain-dev1-output-video', s3_key)

    return s3_key


def replace_audio(video_id,audio_key,base64_audio):
    if base64_audio.startswith('data:audio/wav;base64,'):
        base64_audio = base64_audio.split(',')[1]
    audio_binary = base64.b64decode(base64_audio)
    put_image_in_s3(audio_binary,"soulchain-dev1-output-video",f"generated_videos/{video_id}/audio{audio_key}")

def update_media(df, media_path):
    for media in media_path:
        df.loc[df['path_datalake'] == media, 'count_edit'] += 1

        condition = (df['count_edit'] >= 10) & (df['count_edit'] / df['count_usage'] < 0.5)

        df.loc[(df['path_datalake'] == media) & condition, 'media_state'] = 'not useful'
        
    return df

def update_text_in_json(s3,video_id, lang):
    all_parts_keys=[]
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise
    
        
    video = next((v for v in data if v["video_id"] == video_id), None)

    all_keys = []
    if video and "video_parts" in video:
        all_keys = [part['key'] for part in video['video_parts']]


    if video:
        for text_key in all_keys:
            part = next((p for p in video["video_parts"] if p["key"] == text_key), None)
            if part:
                original_lang=detect(part["text"])
                original_lang = get_argos(original_lang)
                url_translation = "http://127.0.0.1:5003/translate"
                data_subs = {
                    "text": part["text"],
                    "source": original_lang,
                    "target": lang
                }
                response = requests.post(url_translation, json=data_subs)
                sentence=response.text
                part["subtitles"] = sentence

    try:
        data = json.dumps(data)
        s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=data)
    except Exception as e:
        print(f"Error while saving the JSON file: {e}")



def update_text_in_json(s3,video_id, text_keys, new_texts):
    
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')
        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise  

    video = next((v for v in data if v["video_id"] == video_id), None)

    if video:
        for text_key, new_text in zip(text_keys, new_texts):
            part = next((p for p in video["video_parts"] if p["key"] == text_key), None)
            if part:
                part["subtitles"] = new_text
    try:
        data = json.dumps(data)
        s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=data)
    except Exception as e:
        print(f"Error while saving the JSON file: {e}")


def update_media_in_json(s3,video_id,metadata, media_keys, new_media_paths):
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')
        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise  


    video = next((v for v in data if v["video_id"] == video_id), None)

    all_keys = []
    if video and "video_parts" in video:
        all_keys = [part['key'] for part in video['video_parts']]

    if media_keys=="all":
        media_keys= all_keys

    if video:
        for media_key, new_image_path in zip(media_keys, new_media_paths):
            print(media_key)
            part = next((p for p in video["video_parts"] if p["key"] == media_key), None)
            if part:
                old_filepath=part["media_key"]

                metadata=update_media(metadata,old_filepath)
                metadata.to_excel('metadata_mixkit_unsplash_pixabay.xlsx', index=False)
                urls = [item["url"] for item in new_image_path if "url" in item]
                types = [item["type"] for item in new_image_path if "type" in item]
                part["media_key"]=urls
                part["media_type"] = types
    else:
        print("video id not found")
    try:
        data = json.dumps(data)
        s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=data)
        print("JSON file successfully updated.")
    except Exception as e:
        print(f"Error while saving the JSON file: {e}")

def get_first_word_after_slash(input_string):
    parts = input_string.split('/')
    
    last_part = parts[-1]
    
    sub_parts = last_part.split('-')
    
    first_word = sub_parts[0]
    
    return first_word

def change_media(s3,sub,final_keys,video_id, final_video_width, final_video_height,animation, position='bottom',fontsize=34,font_name="Arial-Bold",color='white',bg_color='black'):
    all_parts_keys=[]
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise
    video = next((v for v in data if v["video_id"] == video_id), None)

    all_keys = []
    if video and "video_parts" in video:
        all_keys = [part['key'] for part in video['video_parts']]

    if final_keys=="all":
        final_keys= all_keys


    if video:
        for final_key in final_keys:
            all_parts_keys.append(f"generated_videos/{video_id}/{video_id}_part_{final_key}.mp4")
            part = next((p for p in video["video_parts"] if p["key"] == final_key), None)
            if part:
                indx=final_key

                try:
                    response_audio = s3.get_object(Bucket='soulchain-dev1-output-video', Key=part["audio_key"])
                    audio_data = response_audio['Body'].read()
                except Exception as e:
                    print("Error reading audio from S3:", e)

                with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
                    temp_file.write(audio_data)
                    temp_file.seek(0)  
                    
                    audio = AudioFileClip(temp_file.name)
                    if part:
                       part["duration"] = audio.duration
                try:
                    media_list=[]
                    for media_key in part['media_key']:
                        response = requests.get(media_key)
                        if response.status_code == 200:
                            media_data = response.content
                            media_list.append(media_data)
                        else:
                            print(f"Failed to fetch image from URL:")
                        
                            
                except Exception as e:
                    media_data=[]
                    
                media_data=media_list
                video_types=part["media_type"]

                
                media_clips=[]

                for media, video_type in zip(media_data, video_types):
                    if video_type=='image':
                        l=len(media_data)
                        image_stream = BytesIO(media)
                        image = Image.open(image_stream)
                        image = Image.open(image_stream).convert("RGB")
                        image_np = np.array(image)

                        media_clip = ImageClip(image_np, duration=((audio.duration)/l))
                        media_clip = media_clip.resize((final_video_width, final_video_height))

                        print("animating video")

                        if animation== "True":
                            media_clip = media_clip.resize(lambda t: (final_video_width * (1 + t/10), final_video_height * (1 + t/10)))
                            media_clip = media_clip.set_position(lambda t: ('center', t * 10 + 50))
                            target_width, target_height = final_video_width, final_video_height
                            media_clip = media_clip.resize(lambda t: (
                                int(target_width * (1 + t / 20)),
                                int(target_height * (1 + t / 20))
                            ))

                        media_clips.append(media_clip)
                    
                    if video_type=='video':
                        l=len(media_data)
                        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                            temp_file.write(media)
                            temp_file.seek(0)
                            video_clip = VideoFileClip(temp_file.name)
                            video_clip=video_clip.subclip(4, 10)
                            media_clip = video_clip.subclip(0, (audio.duration)/l)
                            media_clip = media_clip.resize((final_video_width, final_video_height))

                        media_clips.append(media_clip)
                        
                media_clip=concatenate_videoclips(media_clips, method="compose")
                
                media_clip = media_clip.set_audio(audio)

                if sub=='True':
                    text_clip = create_text_updated_clip(part["subtitles"], media_clip, audio.duration,position,fontsize,font_name,color,bg_color)
                    text_clip = text_clip.set_position(position)

                    final_clip = CompositeVideoClip([media_clip, text_clip])

                if sub=='False':
                    final_clip=media_clip

                with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_output_file:
                    temp_output_file_path = temp_output_file.name
                    final_clip.write_videofile(temp_output_file_path, fps=24,audio_codec='aac')


                    try:
                        s3.upload_file(temp_output_file_path, 'soulchain-dev1-output-video',part["video_part_key"])

                    except Exception as e:
                                print("Error uploading final video to S3:", e)

            else:
                print(f"Part with key {final_key} not found.")
    else:
        print(f"Video with ID {video_id} not found.")

    data = json.dumps(data)
        
    s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=data)

    return all_parts_keys


def change_media_url_path(s3,sub,final_keys,video_id, final_video_width, final_video_height,animation, position='bottom',fontsize=34,font_name="Arial-Bold",color='white',bg_color='black'):
    all_parts_keys=[]
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise
    video = next((v for v in data if v["video_id"] == video_id), None)

    all_keys = []
    if video and "video_parts" in video:
        all_keys = [part['key'] for part in video['video_parts']]

    if final_keys=="all":
        final_keys= all_keys


    if video:
        for final_key in final_keys:
            all_parts_keys.append(f"generated_videos/{video_id}/{video_id}_part_{final_key}.mp4")
            part = next((p for p in video["video_parts"] if p["key"] == final_key), None)
            if part:
                indx=final_key

                try:
                    response_audio = s3.get_object(Bucket='soulchain-dev1-output-video', Key=part["audio_key"])
                    audio_data = response_audio['Body'].read()
                except Exception as e:
                    print("Error reading audio from S3:", e)

                with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
                    temp_file.write(audio_data)
                    temp_file.seek(0)  
                    
                    audio = AudioFileClip(temp_file.name)
                    if part:
                       part["duration"] = audio.duration
                try:
                    media_list=[]
                    for media_key in part['media_key']:
                        # response = requests.get(media_key)
                        # if response.status_code == 200:
                        #     media_data = response.content
                        #     media_list.append(media_data)
                        # else:
                        #     print(f"Failed to fetch image from URL:")
                        if media_key.startswith("datalake_media"):
                            # Fetch image from S3 bucket
                            response_image = s3.get_object(Bucket='soulchain-dev1-output-video', Key=media_key)
                            media_data = response_image['Body'].read()
                            print(f"Fetched media from S3: {media_key}")
                        else:
                            # Fetch image from URL
                            response = requests.get(media_key)
                            if response.status_code == 200:
                                media_data = response.content
                                print(f"Fetched media from URL: {media_key}")
                            else:
                                print(f"Failed to fetch image from URL: {media_key}")
                        
                        media_list.append(media_data)
                            
                except Exception as e:
                    media_data=[]
                    
                media_data=media_list
                video_types=part["media_type"]

                
                media_clips=[]

                for media, video_type in zip(media_data, video_types):
                    if video_type=='image':
                        l=len(media_data)
                        image_stream = BytesIO(media)
                        image = Image.open(image_stream)
                        image = Image.open(image_stream).convert("RGB")
                        image_np = np.array(image)

                        media_clip = ImageClip(image_np, duration=((audio.duration)/l))
                        media_clip = media_clip.resize((final_video_width, final_video_height))

                        print("animating video")

                        if animation== "True":
                            media_clip = media_clip.resize(lambda t: (final_video_width * (1 + t/10), final_video_height * (1 + t/10)))
                            media_clip = media_clip.set_position(lambda t: ('center', t * 10 + 50))
                            target_width, target_height = final_video_width, final_video_height
                            media_clip = media_clip.resize(lambda t: (
                                int(target_width * (1 + t / 20)),
                                int(target_height * (1 + t / 20))
                            ))

                        media_clips.append(media_clip)
                    
                    if video_type=='video':
                        l=len(media_data)
                        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                            temp_file.write(media)
                            temp_file.seek(0)
                            video_clip = VideoFileClip(temp_file.name)
                            video_clip=video_clip.subclip(4, 10)
                            media_clip = video_clip.subclip(0, (audio.duration)/l)
                            media_clip = media_clip.resize((final_video_width, final_video_height))

                        media_clips.append(media_clip)
                        
                media_clip=concatenate_videoclips(media_clips, method="compose")
                
                media_clip = media_clip.set_audio(audio)

                if sub=='True':
                    text_clip = create_text_updated_clip(part["subtitles"], media_clip, audio.duration,position,fontsize,font_name,color,bg_color)
                    text_clip = text_clip.set_position(position)

                    final_clip = CompositeVideoClip([media_clip, text_clip])

                if sub=='False':
                    final_clip=media_clip

                with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_output_file:
                    temp_output_file_path = temp_output_file.name
                    final_clip.write_videofile(temp_output_file_path, fps=24,audio_codec='aac')


                    try:
                        s3.upload_file(temp_output_file_path, 'soulchain-dev1-output-video',part["video_part_key"])

                    except Exception as e:
                                print("Error uploading final video to S3:", e)

            else:
                print(f"Part with key {final_key} not found.")
    else:
        print(f"Video with ID {video_id} not found.")

    data = json.dumps(data)
        
    s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=data)

    return all_parts_keys


def change_media_path(s3,sub,final_keys,video_id, final_video_width, final_video_height,animation, position='bottom',fontsize=34,font_name="Arial-Bold",color='white',bg_color='black'):
    all_parts_keys=[]
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            data = []
        else:
            raise
    video = next((v for v in data if v["video_id"] == video_id), None)

    all_keys = []
    if video and "video_parts" in video:
        all_keys = [part['key'] for part in video['video_parts']]

    if final_keys=="all":
        final_keys= all_keys


    if video:
        for final_key in final_keys:
            all_parts_keys.append(f"generated_videos/{video_id}/{video_id}_part_{final_key}.mp4")
            part = next((p for p in video["video_parts"] if p["key"] == final_key), None)
            if part:
                indx=final_key

                try:
                    response_audio = s3.get_object(Bucket='soulchain-dev1-output-video', Key=part["audio_key"])
                    audio_data = response_audio['Body'].read()
                except Exception as e:
                    print("Error reading audio from S3:", e)

                with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
                    temp_file.write(audio_data)
                    temp_file.seek(0)  
                    
                    audio = AudioFileClip(temp_file.name)
                    if part:
                       part["duration"] = audio.duration
                try:
                    media_list=[]
                    for media_key in part['media_key']:
                        response_image = s3.get_object(Bucket='soulchain-dev1-output-video', Key=media_key)
                        media_data = response_image['Body'].read()
                        print(media_data)
                        media_list.append(media_data)
                        
                            
                except Exception as e:
                    media_data=[]
                    
                media_data=media_list

                video_type= video["video_type"]


                if video_type=="mix":
                    video_type=get_first_word_after_slash(part['media_key'])

                if video_type=='image':
                    media_clips=[]
                    for media in media_data:
                        l=len(media_data)
                        image_stream = BytesIO(media)
                        image = Image.open(image_stream)
                        image = Image.open(image_stream).convert("RGB")
                        image_np = np.array(image)

                        media_clip = ImageClip(image_np, duration=((audio.duration)/l))
                        media_clip = media_clip.resize((final_video_width, final_video_height))

                        print("animating video")

                        if animation== "True":
                            media_clip = media_clip.resize(lambda t: (final_video_width * (1 + t/10), final_video_height * (1 + t/10)))
                            media_clip = media_clip.set_position(lambda t: ('center', t * 10 + 50))
                            target_width, target_height = final_video_width, final_video_height
                            media_clip = media_clip.resize(lambda t: (
                                int(target_width * (1 + t / 20)),
                                int(target_height * (1 + t / 20))
                            ))

                        media_clips.append(media_clip)
                    
                    media_clip=concatenate_videoclips(media_clips, method="compose")

                if video_type=='video':
                    media_clips=[]
                    for media in media_data:

                        l=len(media_data)
                        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                            temp_file.write(media)
                            temp_file.seek(0)
                            video_clip = VideoFileClip(temp_file.name)
                            video_clip=video_clip.subclip(4, 10)
                            media_clip = video_clip.subclip(0, (audio.duration)/l)
                            media_clip = media_clip.resize((final_video_width, final_video_height))

                        media_clips.append(media_clip)
                    media_clip=concatenate_videoclips(media_clips, method="compose")

                
                media_clip = media_clip.set_audio(audio)

                if sub=='True':
                    text_clip = create_text_updated_clip(part["subtitles"], media_clip, audio.duration,position,fontsize,font_name,color,bg_color)
                    text_clip = text_clip.set_position(position)

                    final_clip = CompositeVideoClip([media_clip, text_clip])

                if sub=='False':
                    final_clip=media_clip

                with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_output_file:
                    temp_output_file_path = temp_output_file.name
                    final_clip.write_videofile(temp_output_file_path, fps=24,audio_codec='aac')


                    try:
                        s3.upload_file(temp_output_file_path, 'soulchain-dev1-output-video',part["video_part_key"])

                    except Exception as e:
                                print("Error uploading final video to S3:", e)

            else:
                print(f"Part with key {final_key} not found.")

            user_id=video["user_id"]

            file_name = "example.txt"
            file_content = f'video part generated for part {indx}'
            with open(file_name, 'w') as file:
                file.write(file_content)

            s3.upload_file(file_name, 'soulchain-dev1-output-video', f"text_info/{user_id}/example.txt")
    else:
        print(f"Video with ID {video_id} not found.")

    data = json.dumps(data)
        
    s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=data)

    return all_parts_keys















