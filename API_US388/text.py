from moviepy.editor import TextClip,concatenate_videoclips
import requests
from langdetect import detect



def get_argos(lang):
    if lang=='en':
        lang='English'
    if lang=='fr':
        lang='French'
    if lang=='de':
        lang='German'
    if lang=='es':
        lang='Spanish'
    if lang=='pt':
        lang='Portuguese'
    if lang=='ko':
        lang='Korean'
    if lang=='ja':
        lang='Japanese'
    if lang=='ru':
        lang='Russian'
    if lang=='ar':
        lang='Arabic'
    if lang=='it':
        lang='Italian'

    return lang

def def_translation(sentence, lang):
    original_lang = detect(sentence)
    original_lang = get_argos(original_lang)
    print(original_lang)
    
    subtitles = sentence 
    
    if lang != original_lang and lang != "None":
        url_translation = "http://127.0.0.1:5003/translate"
        data = {
            "text": sentence,
            "source": original_lang,
            "target": lang
        }
        print("data:", data)
        response = requests.post(url_translation, json=data)
        subtitles = response.text 
        
    return subtitles

def create_text_clip(lang,sentence, image_clip, audio_duration,position='bottom',fontsize=34,font_name="Arial-Bold",color='white',bg_color='black'):
    original_lang=detect(sentence)
    original_lang = get_argos(original_lang)
    
    if lang != original_lang and lang!="None":
        url_translation = "http://127.0.0.1:5003/translate"
        data = {
            "text": sentence,
            "source": original_lang,
            "target": lang
        }
        print("data:", data)
        response = requests.post(url_translation, json=data)
        sentence=response.text
        print("sentence:", sentence)

    words = sentence.split()
    max_text_width = int(image_clip.size[0] * 0.9) 
    text_clips = []
    
    for i in range(len(words)):
        partial_text = ' '.join(words[:i+1])
        text_frame = TextClip(partial_text, fontsize=fontsize, color=color, bg_color=bg_color, size=(max_text_width, None), method="caption",font=font_name)
        text_frame = text_frame.set_position(position).set_duration(audio_duration / len(words)).margin(bottom=10)
        text_clips.append(text_frame)

    return concatenate_videoclips(text_clips, method="compose"), sentence



def create_text_updated_clip(sentence, image_clip, audio_duration,position,fontsize,font_name,color,bg_color):
    
    words = sentence.split()
    max_text_width = int(image_clip.size[0] * 0.9) 
    text_clips = []
    
    for i in range(len(words)):
        partial_text = ' '.join(words[:i+1])
        text_frame = TextClip(partial_text, fontsize=fontsize, color=color, bg_color=bg_color, size=(max_text_width, None), method="caption",font=font_name)
        text_frame = text_frame.set_position(position)
        text_frame=text_frame.set_duration(audio_duration / len(words))
        text_frame=text_frame.set_pos(('center', position)).margin(bottom=10)
        text_clips.append(text_frame)

    return concatenate_videoclips(text_clips, method="compose")

