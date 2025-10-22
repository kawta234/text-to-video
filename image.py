from io import BytesIO
import io
import numpy as np
import cv2
import uuid
# import boto3
# from botocore.exceptions import ClientError
import os
import json
from datetime import datetime, timedelta
import pandas as pdp
from nltk.stem import PorterStemmer
from PIL import Image
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, CompositeVideoClip
from scrapping_api_image import search_images_for_dataframe_pixabay_video, find_image_for_term 
from text import create_text_clip
import requests
from text_to_media import find_media_best
from langdetect import detect
from text import translate



BASE_FOLDER_TEXT = r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\text_info"
video_info_path = r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\video_info.json"
BASE_FOLDER= r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\generated_videos"

def replace_default_image(image_path_list, processed_image_paths):
    for i in range(len(image_path_list)):
        if image_path_list[i] == "default_image.jpg":
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

def make_video_from_images_test(s3, lang, df, user_id, video_id, api_key, metadata, final_video_width, final_video_height, sub, animation, position='bottom', fontsize=34, font_name="Arial-Bold", color='white', bg_color='black', indx=1):
    add_scene = indx
    metadata_image = metadata[metadata["type"] == 'image']
    metadata_image = metadata_image[metadata_image["media_state"] == 'useful']

    topic_clips = []
    video_parts = []
    processed_terms = set()

    images_folder = r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\images"
    audios_folder = os.path.join(r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\generated_videos", video_id)
    video_parts_folder = audios_folder

    try:
        with open('video_info.json', 'r') as file:
            existing_data_all = json.load(file)
    except FileNotFoundError:
        existing_data_all = []
    except Exception as e:
        raise

    existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]

    processed_image_paths = []
    for entry in existing_data:
        for part in entry['video_parts']:
            if isinstance(part['media_key'], list):
                processed_image_paths.extend(part['media_key'])
            else:
                processed_image_paths.append(part['media_key'])
    print("processed_image_paths: ", processed_image_paths)

    for index, row in df.iterrows():
        sentence = row['sentence']
        print("test:",sentence)
        topic_found = False
        image_found = False

        l = 1

        topics = row['terms']

        topic_found, image_found, image_path_list = find_media_best(topics, processed_image_paths, metadata_image, l)
        image_path_list = replace_default_image(image_path_list, processed_image_paths)

        print(image_path_list)

        if topic_found and image_found:
            print("image_found and topic_found")
            processed_image_paths.extend(image_path_list)

        if not topic_found or not image_found:
            image_path_list = search_images_for_dataframe_pixabay_video(
    row['terms'], 
    api_key, 
    processed_image_paths,  # ← Pass the tracked images
    l
)

            print(image_path_list)
            image_path_list = replace_default_image(image_path_list, processed_image_paths)
            processed_image_paths.extend(image_path_list)

            print(image_path_list)

        audio_path = os.path.join(audios_folder, f"audio{index}.mp3")
        try:
            audio = AudioFileClip(audio_path)
        except Exception as e:
            print("Error reading audio file locally:", e)

        image_clips = []
        print("path lists before iterating", image_path_list)

        for image_path in image_path_list:
            image_duration = audio.duration / len(image_path_list)

            try:
                local_image_path = os.path.join(images_folder, image_path)
                local_image_path = os.path.normpath(local_image_path)
                print("local_image_path", local_image_path)
                image = Image.open(local_image_path).convert("RGB")
                image_np = np.array(image)

                image_clip = ImageClip(image_np, duration=image_duration)
                image_clip = image_clip.resize((final_video_width, final_video_height))

                if animation == "True":
                    image_clip = image_clip.resize(lambda t: (final_video_width * (1 + t / 10), final_video_height * (1 + t / 10)))
                    image_clip = image_clip.set_position(lambda t: ('center', t * 10 + 50))
                    target_width, target_height = final_video_width, final_video_height
                    image_clip = image_clip.resize(lambda t: (
                        int(target_width * (1 + t / 20)),
                        int(target_height * (1 + t / 20))
                    ))

                image_clips.append(image_clip)

            except Exception as e:
                print("Error reading image file locally:", e)

        image_clip = concatenate_videoclips(image_clips, method="compose")
        image_clip = image_clip.set_audio(audio)

        subtitles = None
        if sub == "True":
            print("test2 ::::: ", sentence)
            text_clip, subtitles = create_text_clip(lang, sentence, image_clip, audio.duration, position, fontsize, font_name, color, bg_color)
            print("subtitles", subtitles)
            text_clip = text_clip.set_position(position).margin(bottom=10)

            final_clip = CompositeVideoClip([image_clip, text_clip])
        else:
            final_clip = image_clip
            print("No subtitles")

        output_video_path = os.path.join(video_parts_folder, f"{video_id}_part_{indx}.mp4")
        final_clip.write_videofile(output_video_path, fps=24, audio_codec='aac')

        topic_clips.append(output_video_path)
        types = ["image"] * len(image_path_list)

        video_parts.append({
            'key': indx,
            'duration': audio.duration,
            'media_key': image_path_list,
            'audio_key': audio_path,
            'text': sentence,
            'subtitles': subtitles,
            'video_part_key': output_video_path,
            'media_type': types
        })

        indx += 1
        index += 1

    date_created = datetime.now().isoformat()
    output_data = {
        'video_id': video_id,
        'user_id': user_id,
        'date_created': date_created,
        'video_key': os.path.join(video_parts_folder, "final_video.mp4"),
        'video_type': 'image',
        'video_parts': video_parts
    }

    existing_data_all.append(output_data)

    if add_scene == 1:
        with open(r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\video_info.json", 'w') as json_file:
            json.dump(existing_data_all, json_file)

    return output_data

def generate_final_video(video_id, background_music_file, video_info_path):
    """
    Generate a final video by combining video parts and adding background music, with local file access.

    Args:
        video_id (str): The ID of the video to generate.
        background_music_file (str): Path to the background music file.
        video_info_path (str): Path to the JSON file containing video information.
        media_folder (str): Path to the folder containing video parts.
        output_folder (str): Path to the folder where the final video will be saved.

    Returns:
        str: Path to the generated final video file.
    """
    # Load the background music
    background_music = AudioFileClip(background_music_file)
    background_music = background_music.volumex(0.2)

    # Read video information from the JSON file
    with open(video_info_path, "r") as file:
        data = json.load(file)

    # Gather the video parts for the specified video_id
    topic_clips = [
        part["video_part_key"]
        for video in data
        if video["video_id"] == video_id
        for part in video["video_parts"]
    ]

    # Load video parts into a list of clips
    clips = []
    for clip_path in topic_clips:
        if os.path.exists(clip_path):
            clips.append(VideoFileClip(clip_path))
        else:
            raise FileNotFoundError(f"Video part not found: {clip_path}")

    # Concatenate video clips
    final_video = concatenate_videoclips(clips, method="compose")

    # Trim background music to the final video duration
    background_music = background_music.subclip(0, final_video.duration)

    # Set the audio for the final video
    final_video = final_video.set_audio(CompositeAudioClip([final_video.audio, background_music]))

    # Save the final video to the output folder
    video_info = next((video for video in data if video["video_id"] == video_id), None)

    final_video_path = video_info["video_key"]
    final_video.write_videofile(final_video_path, audio_codec='aac')

    # Clean up resources
    for clip in clips:
        clip.close()

    return final_video_path



def find_media_from_images_test(lang, df, user_id, video_id, api_key, metadata, indx=1):
    add_scene = indx
    metadata_image = metadata[metadata["type"] == 'image']
    metadata_image = metadata_image[metadata_image["media_state"] == 'useful']
    print(metadata_image)
    topic_clips = []
    video_parts = []

    processed_terms = set()

    if os.path.exists(video_info_path):
        with open(video_info_path, 'r') as file:
            existing_data_all = json.load(file)
    else:
        existing_data_all = []

    existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]
    print(existing_data)

    processed_image_paths = []
    for entry in existing_data:
        for part in entry['video_parts']:
            if isinstance(part['media_key'], list):
               processed_image_paths.extend(part['media_key'])
            else:
               processed_image_paths.append(part['media_key'])
    print("processed_image_paths: ", processed_image_paths)

    for index, row in df.iterrows():
        print("start")
        file_name = os.path.join(BASE_FOLDER_TEXT, user_id, "example.txt")
        print(file_name)
        file_content = f'Finding image that matches the topics in part {indx}'
        with open(file_name, 'w') as file:
            file.write(file_content)


        sentence = row['sentence']
        topic_found = False
        image_found = False

        l = 1
        if 50 <= len(sentence) <= 100:
            l = 2
        if len(sentence) > 100:
            l = 3

        topics = row['terms']
        topic_found, image_found, image_path_list = find_media_best(topics, processed_image_paths, metadata_image, l)
        image_path_list = replace_default_image(image_path_list, processed_image_paths)

        print("image_path_list:", image_path_list)

        if topic_found and image_found:
            print("image_found and topic_found")

        if not topic_found or not image_found:
            image_path_list = search_images_for_dataframe_pixabay_video(row['terms'], api_key, [], l)
            image_path_list = replace_default_image(image_path_list, processed_image_paths)

            print("length of list of media:", len(image_path_list))

        try:
            print("trying audio")
            audio_file_path = os.path.join(BASE_FOLDER,video_id,f"audio{index}.mp3")
            with open(audio_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
        except FileNotFoundError:
            print("Error reading audio from local path:", audio_file_path)

        try:
            print("trying video")
            video_part_path = os.path.join(BASE_FOLDER,video_id,f"{video_id}_part_{indx}.mp4")
            print("Successfully created the final video part.")

            topic_clips.append(video_part_path)
            types = ["image"] * len(image_path_list)

            if lang!=None:
                subtitles = translate(sentence, "english", lang)
            else:
                subtitles = sentence

            video_parts.append({
                'key': indx,
                'duration': 0,
                'media_key': image_path_list,
                'audio_key': audio_file_path,
                'text': sentence,
                'subtitles': subtitles,
                'video_part_key': video_part_path,
                'media_type': types
            })

        except Exception as e:
            print("Error processing video part:", e)
        indx += 1

    date_created = datetime.now().isoformat()
    output_data = {
        'video_id': video_id,
        'user_id': user_id,
        'date_created': date_created,
        'video_key': os.path.join(BASE_FOLDER, video_id, "final_video.mp4"),
        'video_type': 'image',
        'video_parts': video_parts
    }

    existing_data_all.append(output_data)

    with open(video_info_path, 'w') as file:
        json.dump(existing_data_all, file)

    with open(file_name, 'w') as file:
        file.write("")

    return output_data