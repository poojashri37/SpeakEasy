# 🎙️ SpeakEasy – Your AI Language Practice Buddy

SpeakEasy is a Streamlit app that lets you practise a language by speaking. Record your voice, and an AI tutor tells you what it heard, corrects your sentence, explains the grammar, and replies so the conversation keeps going.

## Features
- 🗣️ Voice input with speech-to-text (Gnani Vachana)
- ✏️ Correction and short grammar explanation
- 💬 Tutor reply that continues the conversation
- 🔊 Audio of the corrected sentence (only shown when a correction was needed)
- 🔤 For Hindi, Tamil and Kannada: native script, English-letter transliteration and English meaning
- 🎚️ Levels: Beginner, Intermediate, Advanced
- 🌐 Languages: English, Hindi, Tamil, Kannada

## How it works
1. Your recording is sent to **Gnani Vachana STT** and converted to text.
2. **Google Gemini** acts as the tutor and returns the correction, explanation and reply.
3. **Gnani Vachana TTS** speaks the corrected sentence.

## Setup
Requires Python 3.10+.

```bash
git clone <your-repo-url>
cd <repo-folder>
pip install -r requirements.txt
```

Create a `.env` file (copy `.env.example`) and add your keys:

```
GNANI_API_KEY=your_gnani_api_key
GEMINI_API_KEY=your_gemini_api_key
```

`GEMINI_MODEL` is optional. If left empty, the app automatically picks the fastest available Gemini model.

## Run
```bash
streamlit run app.py
```
Open http://localhost:8501 and allow microphone access.

## Project structure
```
app.py            # Streamlit app
requirements.txt  # Dependencies
.env.example      # Template for API keys
```

> Never commit your real `.env` file. It is already listed in `.gitignore`.
