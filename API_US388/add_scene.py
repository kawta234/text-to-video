from topic import find_topics  
from audio import audio_generation
import json
import boto3
from botocore.exceptions import ClientError
import pandas as pd
from image import make_video_from_images_test
from video import make_video_from_video_test
from mix import make_video_parts_mixed
from audio import audio_generation_tts_add_scene

def get_last_key(video):
    if video['video_parts']:
        return max(part['key'] for part in video['video_parts'])
    else:
        return 0 

def generate_video_for_scene(s3,metadata,text,media_type,lang,user_id,video_id,api_key,final_video_width, final_video_height,sub,animation,position,fontsize,font_name,color,bg_color,indx):
    df = find_topics(text)
    df["sentence_part_id"]=indx
   #generate audio 
    if media_type=='image':
        video_parts=make_video_from_images_test(s3,lang,df,user_id,video_id,api_key, metadata,final_video_width, final_video_height,sub,animation,position,fontsize,font_name,color,bg_color,indx)
    if media_type=='video':
        video_parts=make_video_from_video_test(s3,lang,df,user_id,video_id, api_key, metadata,final_video_width, final_video_height,sub,position,fontsize,font_name,color,bg_color,indx)
    if media_type=="mix":
        video_parts=make_video_parts_mixed(s3,lang,df,user_id,video_id, api_key, metadata,final_video_width, final_video_height,sub,position,animation,fontsize,font_name,color,bg_color,indx)


    return video_parts["video_parts"][0]

def add_video_part(s3, video_id, metadata, text, media_type, lang, user_id, api_key, final_video_width, final_video_height, sub,animation,position,fontsize,font_name,color,bg_color):
    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')
        data = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("No video_info.json file found.")
            return
        else:
            raise

    print("done 1")

    video = next((v for v in data if v["video_id"] == video_id), None)

    if video:
        last_key = max(part['key'] for part in video['video_parts']) if video['video_parts'] else 0
        indx = last_key + 1
        audio_generation_tts_add_scene(text,video_id,last_key)
        print("done 2")

        new_video_part = generate_video_for_scene(s3,metadata,text,media_type,lang,user_id,video_id,api_key,final_video_width, final_video_height,sub,animation,position,fontsize,font_name,color,bg_color,indx)
        print("done 3")

        new_video_part["key"] = indx
        new_video_part["video_part_key"] = f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4"
        new_video_part["audio_key"] = f"generated_videos/{video_id}/audio{indx}"
        video['video_parts'].append(new_video_part)
        print("done 4")

    else:
        print(f"No video found with video_id: {video_id}")
        return

    try:
        updated_data = json.dumps(data)
        print("done 5")

        s3.put_object(Bucket='soulchain-dev1-output-video', Key='video_info.json', Body=updated_data)
        print("JSON file successfully updated.")
    except Exception as e:
        print(f"Error while saving the JSON file: {e}")

    return video