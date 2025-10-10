import os
from io import BytesIO
import io
from datalake import put_image_in_s3
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



        try:
            response_audio = s3.get_object(Bucket='soulchain-dev1-output-video', Key=f"generated_videos/{video_id}/audio{indx}")
            audio_data = response_audio['Body'].read()
        except Exception as e:
            print("Error reading audio from S3:", e)

        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(audio_data)
            temp_file.seek(0)  
            
            audio = AudioFileClip(temp_file.name)


        video_clips=[]



        for video_path in video_path_list:

            duration=audio.duration/len(video_path_list)

            try:
                response_video = s3.get_object(Bucket='soulchain-dev1-output-video', Key=video_path)
                video_data = response_video['Body'].read()
            except Exception as e:
                print("Error reading video from S3:", e)
                video_data = None


            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(video_data)
                temp_file.flush()

                video_clip = VideoFileClip(temp_file.name)
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

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_output_file:
            temp_output_file_path = temp_output_file.name
            final_clip.write_videofile(temp_output_file_path, fps=24,audio_codec='aac')

            try:
                key=f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4"
                s3.upload_file(temp_output_file_path, 'soulchain-dev1-output-video', f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4")
                print("Successfully uploaded the final video to S3.")
                topic_clips.append(key)
                if len(video_path_list)==1:
                    types=["video"]
                if len(video_path_list)==2:
                    types=["video","video"]
                if len(video_path_list)==3:
                    types=["video","video","video"]
                video_parts.append({
                    'key':indx,
                    'duration':audio.duration,
                    'media_key': video_path_list,
                    'audio_key': f"generated_videos/{video_id}/audio{indx}",
                    'text':sentence,
                    'subtitles':subtitles,
                    'video_part_key': key,
                    'media_type':types
                })

            except Exception as e:
                print("Error uploading final video to S3:", e)
        indx += 1 
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
        s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=json_data)

    return output_data 

def video_generate_final_video(s3,video_id,background_music_file):

    background_music = AudioFileClip(background_music_file)
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
        file_path = key.split('/')[-1]
        with open(file_path, 'wb') as f:
            f.write(obj['Body'].read())
        clips.append(VideoFileClip(file_path))

    final_video = concatenate_videoclips(clips, method="compose")

    background_music = background_music.subclip(0, final_video.duration)
    final_video = final_video.set_audio(CompositeAudioClip([final_video.audio, background_music]))

    final_video_path = "final_video.mp4"
    final_video.write_videofile(final_video_path,audio_codec='aac')

    with open(final_video_path, "rb") as f:
        s3.upload_fileobj(f, 'soulchain-dev1-output-video', f"generated_videos/{video_id}/final_video.mp4")

    for clip in clips:
        clip.close()
        os.remove(clip.filename)
    os.remove(final_video_path)

    return topic_clips
