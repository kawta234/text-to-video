# 🎬 Text-to-Video Automation Pipeline

An automated pipeline that transforms text input into fully composed videos — combining AI-powered image selection, audio generation, and video assembly into a single streamlined workflow.

---

## 🎯 Problem It Solves

Creating video content manually is slow and expensive.

This system:
- Automatically selects relevant images and video clips based on a text topic
- Generates audio narration from the input text
- Assembles everything into a complete, ready-to-publish video
- Sources media from free stock libraries (Unsplash, Pixabay, Mixkit)

---

## 🧠 How It Works

```
Text Input (topic/script)
        ↓
  Topic Analysis
        ↓
 Media Selection (Images + Videos from stock APIs)
        ↓
  Audio Generation (TTS)
        ↓
  Scene Assembly
        ↓
  Final Video Output 🎬
```

---

## 📁 Project Structure

```
text-to-video/
├── main.py                  # Entry point — orchestrates the full pipeline
├── topic.py                 # Extracts keywords and topic from input text
├── image.py                 # Fetches and filters relevant images
├── video.py                 # Fetches and processes stock video clips
├── audio.py                 # Generates audio narration from text (TTS)
├── text.py                  # Text preprocessing and formatting
├── text_to_media.py         # Maps text segments to matching media
├── add_scene.py             # Assembles scenes with transitions
├── scrapping_api_image.py   # Scrapes image APIs (Unsplash, Pixabay)
├── scrapping_api_video.py   # Scrapes video APIs (Mixkit)
├── requirements.txt         # Python dependencies
└── generated_videos/        # Output folder for generated videos
```

---

## 🛠 Tech Stack

- **Python** — core language
- **MoviePy** — video editing and assembly
- **gTTS / pyttsx3** — text-to-speech audio generation
- **Unsplash API / Pixabay API / Mixkit** — free stock media sources
- **Pandas** — media metadata management
- **Jupyter Notebook** — experimentation and prototyping

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/kawta234/text-to-video.git
cd text-to-video
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up your API keys

Create a `.env` file at the root of the project:

```env
UNSPLASH_ACCESS_KEY=your_unsplash_key
PIXABAY_API_KEY=your_pixabay_key
```

> You can get free API keys at [unsplash.com/developers](https://unsplash.com/developers) and [pixabay.com/api/docs](https://pixabay.com/api/docs/)

### 4. Run the pipeline

```bash
python main.py
```

---

## 📽️ Example Output

> *(Add a screenshot or GIF of a generated video here)*

---

## 🔮 Future Improvements

- Web interface (Flask/Streamlit) for non-technical users
- Support for custom voice selection
- Automatic subtitle generation
- Integration with YouTube/TikTok upload API
- Support for multiple languages

---

## 📄 License

MIT License — free to use and modify.

---

*Developed by **Kawtar CHAKIR** — AI/ML Engineer .*
