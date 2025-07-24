import streamlit as st
from websocket import WebSocketApp
import threading
import queue
import time
from streamlit.runtime.scriptrunner import add_script_run_ctx

st.set_page_config(page_title="Cockpit Assistant", layout="centered")
st.title("🎧 Cockpit Voice Command System")
st.markdown("Press start to activate the assistant.")

WEBSOCKET_URL = "ws://localhost:8000/ws"
message_queue = queue.Queue()

# Callbacks
def on_message(ws, message):
    print("[WS Message]", message)
    message_queue.put("📥 " + message)

def on_open(ws):
    print("[WS Open]")
    message_queue.put("✅ WebSocket connection established.")

def on_error(ws, error):
    print("[WS Error]", error)
    message_queue.put(f"❌ Error: {error}")

def on_close(ws, code, msg):
    print("[WS Closed]")
    message_queue.put("🔌 Connection closed")

def start_ws_client():
    ws = WebSocketApp(
        WEBSOCKET_URL,
        on_message=on_message,
        on_open=on_open,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# === Streamlit Session State ===
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# === Start Button ===
if st.button("🎤 Start Listening") and not st.session_state.ws_thread:
    t = threading.Thread(target=start_ws_client, daemon=True)
    add_script_run_ctx(t)  # Enables thread use in Streamlit
    t.start()
    st.session_state.ws_thread = t
    st.success("🟢 Listening started...")

# === Display Messages (Live) ===
st.markdown("### 📢 System Output")
output_box = st.empty()

# === Update Display Every Second ===
while True:
    new_messages = []
    while not message_queue.empty():
        new_messages.append(message_queue.get())

    if new_messages:
        st.session_state.messages.extend(new_messages)
        with output_box.container():
            for msg in st.session_state.messages[-30:]:
                st.write(msg)

    time.sleep(1)

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import queue
import pyaudio
import torch
import numpy as np
import whisper
from vosk import Model as VoskModel, KaldiRecognizer
import json
import difflib
import wave
import time

# Load commands
base_dir = os.path.dirname(os.path.dirname(__file__))
with open(os.path.join(base_dir, "utils", "commands.json")) as f:
    COMMANDS = json.load(f)

# Trigger words
TRIGGER_WORDS = ["system"]

# Models
whisper_model = whisper.load_model("medium")
vosk_model = VoskModel(os.path.join(base_dir, "models", "vosk"))
vosk_recognizer = KaldiRecognizer(vosk_model, 16000)
vosk_recognizer.SetWords(True)

# Audio config
RATE = 16000
CHUNK = 1024
CHANNELS = 1
FORMAT = pyaudio.paInt16

audio_queue = queue.Queue()

def audio_callback(in_data, frame_count, time_info, status):
    audio_queue.put(in_data)
    return (None, pyaudio.paContinue)

def start_microphone_stream():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                    frames_per_buffer=CHUNK, stream_callback=audio_callback)
    stream.start_stream()
    return stream

def detect_trigger(audio_data):
    if vosk_recognizer.AcceptWaveform(audio_data):
        result = json.loads(vosk_recognizer.Result())
        text = result.get("text", "").lower()
        return any(w in text for w in TRIGGER_WORDS), text
    return False, ""

def transcribe_whisper(frames):
    audio = np.frombuffer(b''.join(frames), np.int16).astype(np.float32) / 32768.0
    result = whisper_model.transcribe(audio, language="en")
    return result.get("text", "").strip()

def match_command(text):
    matches = difflib.get_close_matches(text.lower(), [cmd.lower() for cmd in COMMANDS], n=1, cutoff=0.6)
    return matches[0] if matches else None

async def main_loop_websocket(websocket):
    await websocket.accept()
    print("🔗 WebSocket accepted")  # Add this
    await websocket.send_text("🟢 System online. Say trigger word: 'system'")
    print("📤 Message sent")  # Add this
    
    stream = start_microphone_stream()
    frames = []
    triggered = False
    silence_count = 0

    try:
        while True:
            if not audio_queue.empty():
                audio_data = audio_queue.get()
                frames.append(audio_data)

                is_triggered, trigger_text = detect_trigger(audio_data)
                if is_triggered and not triggered:
                    triggered = True
                    await websocket.send_text(f"🎯 Trigger Detected: '{trigger_text}'")
                    frames = []
                    silence_count = 0
                    continue

                if triggered:
                    silence_count += 1
                    if silence_count > 30:
                        await websocket.send_text("📝 Transcribing...")
                        transcript = transcribe_whisper(frames)
                        await websocket.send_text(f"🗣️ Transcript: {transcript}")
                        command = match_command(transcript)
                        if command:
                            await websocket.send_text(f"✅ Matched Command: {command}")
                        else:
                            await websocket.send_text("❌ Command not recognized.")
                        triggered = False
                        frames = []
                        await websocket.send_text("🕐 Listening for trigger again...")
    except Exception as e:
        await websocket.send_text(f"❌ Error: {str(e)}")
        stream.stop_stream()
        stream.close() this is my inference streamlit and from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from inference.inference_streamlit import main_loop_websocket

app = FastAPI()

# Allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await main_loop_websocket(websocket) this is my backend app    