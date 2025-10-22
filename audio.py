import requests
import time  
from elevenlabs import Voice, VoiceSettings, generate, save
import elevenlabs
import tempfile
from pathlib import Path




def audio_generation(df, video_id, eleven_api='sk_110e4afdb18b36afae07c4439b38a8c5f777fe981aa74196'):
    elevenlabs.set_api_key(eleven_api)
    for sentence_id, sentence in zip(df['sentence_part_id'], df['sentence']):
        audio = generate(
            text=sentence,
            voice=Voice(
                voice_id='DPn1nkTOkN7dmZpazZS5',
                settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True)
            )
        )
        base_dir = Path(r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\generated_videos") / str(video_id)
        base_dir.mkdir(parents=True, exist_ok=True)

        dest_path = base_dir / f"audio{sentence_id}.mp3"
        with open(dest_path, "wb") as f:
            f.write(audio)

