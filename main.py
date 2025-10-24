from topic import find_topics
from audio import audio_generation
from video import make_video_from_video_test
from image import make_video_from_images_test,find_media_from_images_test,generate_final_video

import os
import json
import requests
import uuid
from flask import Flask, request
from flask.json import jsonify
import pandas as pd
import os
import spacy.cli
from flask import Flask
from flask_cors import CORS
import logging


os.environ["TOKENIZERS_PARALLELISM"] = "false"

from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": r"C:\Users\admin\Downloads\ImageMagick-7.1.1-Q16\ImageMagick-7.1.1-Q16\magick.exe"})

import spacy.cli.download





app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:4200"}})



metadata = pd.read_excel(r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\new_metadata_mixkit_unsplash_pixabay-4.xlsx")
BASE_FOLDER_TEXT = r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\text_info"

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

        video_id= f"video_{user_id}"
        metadata=pd.read_excel(r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\new_metadata_mixkit_unsplash_pixabay-4.xlsx")
        if final_video_width>final_video_height:
            size="horizontal"
        if final_video_width<final_video_height: 
            size="vertical"
        if final_video_width==final_video_height:
            size="square"

        metadata = metadata[metadata["size"] == size]


        df = find_topics(text)
        print(df)
        
        s3=""
        audio_generation(df,video_id)

        if video_type == 'image':
            topic_clips = make_video_from_images_test(s3,language,df,user_id,video_id, pixabay_api_key, metadata,final_video_width, final_video_height, sub,animation)
            return jsonify({'video_info':topic_clips})
        
        elif video_type == 'video':
            topic_clips = make_video_from_video_test(s3,language,df,user_id,video_id, pixabay_api_key, metadata,final_video_width, final_video_height,sub)
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
        file=r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388"
        background_music_path=os.path.join(file, background_music_file)
        video_info_path=r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\video_info.json"
        url=generate_final_video(video_id,background_music_path, video_info_path)
        return jsonify({'Final video generated':url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)