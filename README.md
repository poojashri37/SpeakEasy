# SpeakEasy – Your AI Language Practice Buddy

Languages: English, Hindi, Tamil, Kannada. Levels: Beginner / Intermediate / Advanced.

Flow: record voice -> Gnani Vachana STT -> Gemini tutor (what I heard, correction, explanation, reply) -> Gnani TTS audio of the corrected sentence.

## Run
```
pip install -r requirements.txt
cp .env.example .env     # add your GNANI_API_KEY and GEMINI_API_KEY
streamlit run app.py
```
Open http://localhost:8501
