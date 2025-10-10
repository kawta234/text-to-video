from text import def_translation
from datetime import datetime, timedelta
import json
from botocore.exceptions import ClientError
import pandas as pd
from audio import audio_generation_tts
import boto3


def read_txt_from_s3(bucket_name, file_key):
    s3 = boto3.client('s3', aws_access_key_id="AKIAUJXLE2HEM4YQVOSA",aws_secret_access_key="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", region_name='eu-west-1')
    
    obj = s3.get_object(Bucket=bucket_name, Key=file_key)
    
    text = obj['Body'].read().decode('utf-8')
    
    return text

def split_text(s3,lang,df,user_id,video_id):

    try:
        response = s3.get_object(Bucket='soulchain-dev1-output-video', Key='video_info.json')

        existing_data_all = json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            existing_data_all = []
        else:
            raise
    indx=1
    topic_clips=[]
    video_parts=[]

    for index, row in df.iterrows():
        
        sentence = row['sentence']
        subtitles=def_translation(sentence,lang)
        key=f"generated_videos/{video_id}/{video_id}_part_{indx}.mp4"
        topic_clips.append(key)
        video_parts.append({
            'key':indx,
            'duration':0,
            'media_key': [],
            'audio_key': f"generated_videos/{video_id}/audio{indx}",
            'text':sentence,
            'subtitles':subtitles,
            'video_part_key': key,
            'media_type':[]
        })
        indx += 1

    date_created = datetime.now().isoformat() 
    output_data = {
        'video_id': video_id,
        'user_id': user_id,
        'date_created':date_created,
        'video_key':f"generated_videos/{video_id}/final_video.mp4",
        'video_type':'mix',
        'video_parts': video_parts
        }
    
    existing_data_all.append(output_data)

    json_data = json.dumps(existing_data_all)
        
    s3.put_object(Bucket='soulchain-dev1-output-video', Key=f"video_info.json", Body=json_data)

    return output_data


def generate_manual_audio(s3,video_id):
    df=[]
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
        final_keys = [part['key'] for part in video['video_parts']]

    if video:
        for final_key in final_keys:
            part = next((p for p in video["video_parts"] if p["key"] == final_key), None)
            df.append({
                        'sentence':part["text"],
                        'sentence_part_id':part["key"]-1
                    })
            
    df=pd.DataFrame(df) 

    audio_generation_tts(df, video_id)

    

