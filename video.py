import os
from io import BytesIO
import io
import json 
import tempfile
from datetime import datetime
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, CompositeVideoClip
from botocore.exceptions import ClientError
from scrapping_api_video import search_video_for_dataframe_pixabay_video, find_video_for_term
from text import create_text_clip
from text_to_media import find_media_best




def replace_default_video(image_path_list, processed_image_paths):
    for i in range(len(image_path_list)):
        if image_path_list[i] == "datalake_media/default_video.mp4":
            if i > 0:
                image_path_list[i] = image_path_list[i - 1]
            else:
                image_path_list[i] = processed_image_paths[-1]
    return image_path_list



def make_video_from_video_test(s3,lang,df,user_id,video_id, api_key, metadata,final_video_width, final_video_height,sub,position='bottom',fontsize=34,font_name="Arial-Bold",color='white',bg_color='black',indx=1):
    
    add_scene=indx
    metadata_video = metadata[metadata["type"] == 'video']
    metadata_video = metadata_video[metadata_video["media_state"] == 'useful']  
    print(metadata_video)
    topic_clips = []
    video_parts = []

    images_folder = r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\images"
    audios_folder = os.path.join(r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\generated_videos", video_id)
    video_parts_folder = audios_folder

    processed_terms = set()  



    ### retrieving the json file  

    try:
        with open('video_info.json', 'r') as file:
            existing_data_all = json.load(file)
    except FileNotFoundError:
        existing_data_all = []
    except Exception as e:
        raise
        
    existing_data = [entry for entry in existing_data_all if entry['user_id'] == user_id]


    processed_video_paths = []
    for entry in existing_data:
        processed_video_paths.extend([part['media_key'] for part in entry['video_parts']])
    print("processed_video_paths: ",processed_video_paths)
 

    for index, row in df.iterrows():
        sentence = row['sentence']
        topic_found = False
        video_found = False
        l=1

        if 50<=len(sentence)<=100:
            l=2
        if len(sentence)>100:
            l=3
        topics =row['terms']
        print(topics)
        topic_found, video_found,video_path_list = find_media_best(topics, processed_video_paths, metadata_video) 
        video_path_list=replace_default_video(video_path_list,processed_video_paths)
  
                    
        if topic_found and video_found:
            print("video_found and topic_found")
            processed_video_paths.append(video_path_list) 
            

        if not topic_found or not video_found:
            video_path_list = search_video_for_dataframe_pixabay_video(row['terms'], api_key,processed_video_paths)
            video_path_list=replace_default_video(video_path_list,processed_video_paths)

            processed_video_paths.append(video_path_list) 



        audio_path = os.path.join(audios_folder, f"audio{index}.mp3")
        try:
            audio = AudioFileClip(audio_path)
        except Exception as e:
            print("Error reading audio file locally:", e)


        video_clips=[]



        for video_path in video_path_list:

            duration=audio.duration/len(video_path_list)

            video_clip = VideoFileClip(video_path)
            video_clip = video_clip.resize((final_video_width, final_video_height))
            video_clip = video_clip.set_duration(duration)
            
            video_clips.append(video_clip)

        video_clip=concatenate_videoclips(video_clips, method="compose")

        video_clip = video_clip.set_audio(audio)

        subtitles = None
    
        if sub == "True":
            text_clip,subtitles = create_text_clip(lang,sentence, video_clip, audio.duration,position,fontsize,font_name,color,bg_color)
            text_clip = text_clip.set_position(position)
            final_clip = CompositeVideoClip([video_clip, text_clip])
        else: 
            final_clip=video_clip
            print("No subtitles")

        output_video_path = os.path.join(video_parts_folder, f"{video_id}_part_{indx}.mp4")
        final_clip.write_videofile(output_video_path, fps=24, audio_codec='aac')

        topic_clips.append(output_video_path)
        types = ["video"] * len(video_path_list)
            
        video_parts.append({
            'key':indx,
            'duration':audio.duration,
            'media_key': video_path_list,
            'audio_key': f"generated_videos/{video_id}/audio{index}",
            'text':sentence,
            'subtitles':subtitles,
            'video_part_key': output_video_path,
            'media_type':types
        })

        
        indx += 1
        index += 1 
    print(topic_clips)


    date_created = datetime.now().isoformat() 


    output_data = {
    'video_id': video_id,
    'user_id': user_id,
    'date_created':date_created,
    'video_key':f"generated_videos/{video_id}/final_video.mp4",
    'video_type':'video',
    'video_parts': video_parts
    }

    existing_data_all.append(output_data)


    json_data = json.dumps(existing_data_all)
        
    if add_scene == 1:
        with open('video_info.json', 'w') as json_file:
            json.dump(existing_data_all, json_file)

    return output_data