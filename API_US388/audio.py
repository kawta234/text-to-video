from datalake import put_image_in_s3
import requests
import time  
from elevenlabs import Voice, VoiceSettings, generate, save
import elevenlabs
import tempfile


def audio_generation(s3, df, video_id, eleven_api):
    elevenlabs.set_api_key(eleven_api)
    for sentence_id, sentence in zip(df['sentence_part_id'], df['sentence']):
        audio = generate(
            text=sentence,
            voice=Voice(
                voice_id='EXAVITQu4vr4xnSDxMaL',
                settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True)
            )
        )
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(audio)
            temp_file.seek(0)
            s3.upload_file(temp_file.name, 'soulchain-dev1-output-video', f"generated_videos/{video_id}/audio{sentence_id+1}")


def audio_generation_tts(df, video_id):
    for sentence_id, sentence in zip(df['sentence_part_id'], df['sentence']):
        url_tts = "http://127.0.0.1:5013/tts/tts"
        data = {
            "text": sentence,
            "video_id":video_id,
            "sentence_id":sentence_id,
            "chemin":"voices/test_sounny.mp3"
        }
        response = requests.post(url_tts, json=data)
        if response==200:
            print("audio done")
        else: 
            print("audio error")


def audio_generation_tts_add_scene(sentence,video_id,sentence_id):
    url_tts = "http://127.0.0.1:5013/tts/tts"
    data = {
        "text": sentence,
        "video_id":video_id,
        "sentence_id":sentence_id,
        "chemin":"voices/test_sounny.mp3"

    }
    response = requests.post(url_tts, json=data)
    if response==200:
        print("audio done")
    else: 
        print("audio error")


def generate_audio(df,video_id):
    auth_url = "https://b9wsnd2xv7.execute-api.eu-west-1.amazonaws.com/Prod/api/auth/login"
    login_payload = {
        "username": "usernametest11",  
        "password": "P@ssword123"   
    }

    response = requests.post(auth_url, json=login_payload)

    if response.status_code == 200:
        access_token = response.json().get("accessToken")
    else:
        raise Exception("Login failed")


    launch_url = "https://v2qd79hg57.execute-api.eu-west-1.amazonaws.com/prod/launch"
    launch_headers = {
        "Authorization":f"{access_token}"
    }

    for sentence_id, sentence in zip(df['sentence_part_id'], df['sentence']):


        launch_payload = {
            
            "username": "usernametest11",
            "text": sentence
        }

        response = requests.post(launch_url, headers=launch_headers, json=launch_payload)

        if response.status_code == 200:
            execution_id = response.json().get("execution_id")

        check_url = f"https://v2qd79hg57.execute-api.eu-west-1.amazonaws.com/prod/check?execution_id={execution_id}"
        check_headers = {
            "Authorization": f"{access_token}"
        }

        status = None
        while status != "success":
            response = requests.get(check_url, headers=check_headers)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                output_path = data.get("output_path")

                if status == "success":
                    # Process completed, you could handle output_path here
                    pass  # or do something else instead of printing
                else:
                    time.sleep(10)  # wait 5 seconds before retrying

        output_bucket = "soulchain-dev1-output-video"
        s3_key = f"generated_videos/{video_id}/audio{sentence_id}"

        put_image_in_s3(output_path, output_bucket, s3_key)


    return output_path
    


