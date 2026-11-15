"""SpeakEasy - Your AI Language Practice Buddy
Voice in (Gnani Vachana STT) -> tutor feedback (Gemini) -> voice out (Gnani Vachana TTS)
"""
import json
import os
import time

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

GNANI_API_KEY = os.getenv("GNANI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()  # leave empty to auto-pick the fastest model

STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

LANGUAGES = {
    "English": {"code": "en-IN", "voice": "Nalini", "native": False},
    "Hindi": {"code": "hi-IN", "voice": "Nalini", "native": True},
    "Tamil": {"code": "ta-IN", "voice": "Nalini", "native": True},
    "Kannada": {"code": "kn-IN", "voice": "Nalini", "native": True},
}
LEVELS = ["Beginner", "Intermediate", "Advanced"]


# ---------------------------------------------------------------- Gnani STT
def transcribe(audio_bytes: bytes, language_code: str) -> str:
    resp = requests.post(
        STT_URL,
        headers={"X-API-Key-ID": GNANI_API_KEY},
        files={"audio_file": ("recording.wav", audio_bytes, "audio/wav")},
        data={"language_code": language_code, "model": "prisma-v3.0", "format": "transcribe"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success", True):
        raise RuntimeError(data.get("error", {}).get("message", "STT failed"))
    return (data.get("transcript") or "").strip()


# ---------------------------------------------------------------- Gnani TTS
def synthesize(text: str, language_code: str, voice: str) -> bytes | None:
    try:
        resp = requests.post(
            TTS_URL,
            headers={"Content-Type": "application/json", "X-API-Key-ID": GNANI_API_KEY},
            json={
                "text": text,
                "voice": voice,
                "model": "timbre-v2.5",
                "language": language_code,
                "speed": 1.0,
                "audio_config": {
                    "sample_rate": 24000,
                    "num_channels": 1,
                    "sample_width": 2,
                    "encoding": "linear_pcm",
                    "container": "wav",
                },
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as exc:  # TTS is optional - never break the lesson
        st.warning(f"Could not generate audio: {exc}")
        return None


# ---------------------------------------------------------------- Tutor LLM
def build_prompt(language: str, level: str, native: bool, transcript: str, history: list) -> str:
    script_rules = (
        f"""For the fields "heard" and "reply", write the {language} text in its native script,
then give a Roman-letter transliteration ("heard_roman" / "reply_roman") and an English meaning
("heard_meaning" / "reply_meaning")."""
        if native
        else """Set "heard_roman", "heard_meaning", "reply_roman" and "reply_meaning" to empty strings."""
    )
    past = "\n".join(f"{m['role']}: {m['text']}" for m in history[-6:])
    return f"""You are a friendly, patient {language} language tutor. The learner's level is {level}.
Keep your language simple and suitable for that level.

Conversation so far:
{past or '(none)'}

The learner just said (speech-to-text transcript): "{transcript}"

{script_rules}

Respond ONLY with JSON using exactly these keys:
{{
  "heard": "what the learner said",
  "heard_roman": "...",
  "heard_meaning": "...",
  "correction": "the corrected sentence in {language}, or 'No correction needed! Your sentence is correct.'",
  "explanation": "short grammar explanation in English (or say there are no mistakes)",
  "reply": "your natural reply in {language} that continues the conversation and ends with a question",
  "reply_roman": "...",
  "reply_meaning": "..."
}}"""


@st.cache_resource(show_spinner=False)
def pick_model() -> str:
    """Use GEMINI_MODEL if set, else ask Google which models this key can use
    and choose the fastest one (flash-lite first, then flash)."""
    if GEMINI_MODEL:
        return GEMINI_MODEL
    resp = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
        headers={"x-goog-api-key": GEMINI_API_KEY},
        timeout=20,
    )
    resp.raise_for_status()
    names = [
        m["name"].split("/", 1)[1]
        for m in resp.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    skip = ("preview", "exp", "tts", "image", "audio", "live", "thinking", "robotics", "computer", "embedding")
    stable = [n for n in names if n.startswith("gemini") and not any(k in n for k in skip)]
    for key in ("flash-lite", "flash"):
        matches = sorted((n for n in stable if key in n and (key == "flash-lite" or "lite" not in n)), reverse=True)
        if matches:
            return matches[0]
    raise RuntimeError("No usable Gemini model found for this API key")


def ask_tutor(language: str, level: str, native: bool, transcript: str, history: list) -> dict:
    body = {
        "contents": [{"parts": [{"text": build_prompt(language, level, native, transcript, history)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.6},
    }
    last_exc = None
    for attempt in range(2):  # retry on timeouts / temporary overload
        try:
            resp = requests.post(
                GEMINI_URL.format(model=pick_model()),
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json=body,
                timeout=(10, 30),
            )
            if resp.status_code in (429, 500, 503):
                last_exc = RuntimeError(f"Gemini busy (HTTP {resp.status_code})")
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Gemini did not respond after 2 tries: {last_exc}")


# ---------------------------------------------------------------- UI helpers
def render_tutor_message(language: str, native: bool, msg: dict) -> None:
    d = msg["data"]
    label = language
    st.markdown("**🎧 WHAT I HEARD:**")
    st.markdown(f"**{label}:** {d.get('heard', '')}")
    if native:
        st.markdown(f"**{label} in English Letters:** {d.get('heard_roman', '')}")
        st.markdown(f"**English Meaning:** {d.get('heard_meaning', '')}")
    st.markdown("**✏️ CORRECTION:**")
    st.write(d.get("correction", ""))
    st.markdown("**💡 EXPLANATION:**")
    st.write(d.get("explanation", ""))
    st.markdown("**💬 YOUR AI TUTOR:**")
    st.markdown(f"**{label}:** {d.get('reply', '')}")
    if native:
        st.markdown(f"**{label} in English Letters:** {d.get('reply_roman', '')}")
        st.markdown(f"**English Meaning:** {d.get('reply_meaning', '')}")
    if msg.get("audio"):
        st.caption("🔊 Listen to the corrected sentence:")
        st.audio(msg["audio"], format="audio/wav")


# ---------------------------------------------------------------- App
st.set_page_config(page_title="SpeakEasy", page_icon="🎙️")
st.title("🎙️ SpeakEasy")
st.subheader("Your AI Language Practice Buddy")
st.write("Practice languages, improve your grammar and build confidence through conversations!")

if not GNANI_API_KEY or not GEMINI_API_KEY:
    st.error("Missing API keys. Copy `.env.example` to `.env` and fill in GNANI_API_KEY and GEMINI_API_KEY.")
    st.stop()

st.divider()
language = st.selectbox("Choose your practice language:", list(LANGUAGES))
level = st.selectbox("Choose your level:", LEVELS)
cfg = LANGUAGES[language]

if "history" not in st.session_state:
    st.session_state.history = []
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0
if "last_processed" not in st.session_state:
    st.session_state.last_processed = None

st.divider()
st.header("💬 Your Conversation")
if not st.session_state.history:
    st.info("Start practising by recording your first message below!")
for m in st.session_state.history:
    if m["role"] == "user":
        with st.chat_message("user"):
            st.write("🎙️ Voice message")
    else:
        with st.chat_message("assistant"):
            render_tutor_message(language, cfg["native"], m)

st.divider()
st.header("🎙️ Practise by speaking")
st.write("Record your answer to the AI tutor. Speak in your selected practice language.")
audio = st.audio_input("Record your voice", key=f"audio_{st.session_state.audio_key}")

if audio is not None:
    audio_bytes = audio.getvalue()
    sig = hash(audio_bytes)
    if sig != st.session_state.last_processed:
        st.session_state.last_processed = sig
        try:
            with st.spinner("Listening to your voice..."):
                transcript = transcribe(audio_bytes, cfg["code"])
            if not transcript:
                st.warning("I couldn't hear anything. Please try again.")
            else:
                with st.spinner(f"Your tutor is thinking... ({pick_model()})"):
                    data = ask_tutor(language, level, cfg["native"], transcript, st.session_state.history)
                tts_text = data.get("correction", "")
                # sentence already correct -> no corrected-sentence audio
                if not tts_text or tts_text.lower().startswith("no correction"):
                    wav = None
                else:
                    wav = synthesize(tts_text, cfg["code"], cfg["voice"])
                st.session_state.history.append({"role": "user", "text": transcript})
                st.session_state.history.append(
                    {"role": "tutor", "text": data.get("reply", ""), "data": data, "audio": wav}
                )
                # reset the recorder so it is ready for the next answer
                st.session_state.audio_key += 1
                st.rerun()
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

st.divider()
if st.button("🗑️ Clear Conversation", use_container_width=True):
    st.session_state.history = []
    st.session_state.audio_key += 1
    st.session_state.last_processed = None
    st.rerun()
