import requests
import os
from text import create_text_clip
from moviepy.editor import VideoFileClip, ImageClip,TextClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, CompositeVideoClip
import cv2
from PIL import Image
import io
import random
import pandas as pd
from botocore.exceptions import ClientError
from scrapping_api_video import search_video_for_dataframe_pixabay_video, find_video_for_term
from text import create_text_clip
import json
from datalake import put_image_in_s3
from scrapping_api_image import find_image_for_term,search_images_for_dataframe_pixabay_video
from scrapping_api_video import find_video_for_term
import tempfile
import numpy as np
from io import BytesIO
from datetime import datetime
from text_to_media import find_media_best



def make_video_parts_mixed(s3, lang, df, user_id, video_id, api_key, metadata, final_video_width, final_video_height, sub,animation,position='bottom',fontsize=34,font_name="Arial-Bold",color='white',bg_color='black', indx=1):
    
    metadata_video = metadata[metadata["type"] == 'video']
    metadata_video = metadata_video[metadata_video["media_state"] == 'useful']

    metadata_image = metadata[metadata["type"] == 'image']
    metadata_image = metadata_image[metadata_image["media_state"] == 'useful']

    topic_clips = []
    video_parts = []
    processed_terms = set()

    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')
        existing_data_all = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data_all = []
        else:
            raise

    existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]

    processed_media_paths = [part['media_key'] for entry in existing_data for part in entry['video_parts']]
    print("processed_media_paths: ", processed_media_paths)

    for index, row in df.iterrows():
        sentence = row['sentence']
        sentence_id = row['sentence_part_id']
        media_found = False
        video_found = False
        image_found = False

        topics = row['terms']

        print("finding in datalake")
        topic_found, video_found, video_path = find_media_best(topics, processed_media_paths, metadata_video)
        if video_found:
            print("video_found")
            media_path = video_path
            processed_media_paths.append(media_path)
        else:
            topic_found, image_found, image_path = find_media_best(topics, processed_media_paths, metadata_image)
            if image_found:
                print("image_found")
                media_path = image_path
                processed_media_paths.append(media_path)
            else:
                media_path = search_images_for_dataframe_pixabay_video(row['terms'], api_key, processed_media_paths)
                processed_media_paths.append(media_path)

        if media_path != "datalake_media/default_video.mp4":
            metadata.loc[metadata['path_datalake'] == media_path, 'count_usage'] += 1
            with io.BytesIO() as buffer:
                metadata.to_excel(buffer, index=False)
                buffer.seek(0)
                data_bytes = buffer.read()
            put_image_in_s3(data_bytes, "soulchain-dev1-output-video", "metadata_mixkit_unsplash_pixabay.xlsx")

        try:
            response_audio = s3.get_object(Bucket='soulchain-dev1-output-video', Key=f"generated_videos/{video_id}/audio{indx}")
            audio_data = response_audio['Body'].read()
        except Exception as e:
            print("Error reading audio from S3:", e)

        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(audio_data)
            temp_file.seek(0)
            audio = AudioFileClip(temp_file.name)

        if video_found:
            try:
                response_video = s3.get_object(Bucket='soulchain-dev1-output-video', Key=media_path)
                video_data = response_video['Body'].read()
            except Exception as e:
                print("Error reading video from S3:", e)
                video_data = None

            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(video_data)
                temp_file.flush()
                video_clip = VideoFileClip(temp_file.name)
                video_clip = video_clip.resize((final_video_width, final_video_height))
                video_clip = video_clip.set_duration(audio.duration).set_audio(audio)
                media_clip = video_clip

        elif image_found:
            try:
                response_image = s3.get_object(Bucket='soulchain-dev1-output-video', Key=media_path)
                image_data = response_image['Body'].read()
            except Exception as e:
                print("Error reading image from S3:", e)
                image_data = None

            image_stream = BytesIO(image_data)
            image = Image.open(image_stream).convert("RGB")
            image_np = np.array(image)
            image_clip = ImageClip(image_np, duration=(audio.duration))
            image_clip = image_clip.resize((final_video_width, final_video_height))
            image_clip = image_clip.set_audio(audio)
            if animation=="True":
                image_clip = image_clip.resize(lambda t: (final_video_width * (1 + t/10), final_video_height * (1 + t/10)))
                image_clip = image_clip.set_position(lambda t: ('center', t * 10 + 50))
                target_width, target_height = final_video_width, final_video_height
                image_clip = image_clip.resize(lambda t: (
                    int(target_width * (1 + t / 20)),
                    int(target_height * (1 + t / 20))
                ))
            media_clip = image_clip

        subtitles = None
        if sub == "True":
            text_clip, subtitles = create_text_clip(lang, sentence, media_clip, audio.duration,position,fontsize,font_name,color,bg_color)
            text_clip = text_clip.set_position('bottom')
            final_clip = CompositeVideoClip([media_clip, text_clip])
        else:
            final_clip = media_clip
            print("No subtitles")

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_output_file:
            temp_output_file_path = temp_output_file.name
            final_clip.write_videofile(temp_output_file_path, fps=24, audio_codec='aac')

            try:
                key = f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4"
                s3.upload_file(temp_output_file_path, 'soulchain-dev1-output-video', key)
                print("Successfully uploaded the final video to S3.")
                topic_clips.append(key)
                video_parts.append({
                    'key': indx,
                    'duration': audio.duration,
                    'media_key': media_path,
                    'audio_key': f"generated_videos/{video_id}/audio{indx}",
                    'text': sentence,
                    'subtitles': subtitles,
                    'video_part_key': key
                })
            except Exception as e:
                print("Error uploading final video to S3:", e)
        indx += 1

    date_created = datetime.now().isoformat()
    output_data = {
        'video_id': video_id,
        'user_id': user_id,
        'date_created': date_created,
        'video_key': f"generated_videos/{video_id}/final_video.mp4",
        'video_type': 'mix',
        'video_parts': video_parts
    }

    existing_data_all.append(output_data)
    json_data = json.dumps(existing_data_all)
    s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=json_data)

    return output_data
