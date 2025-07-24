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
import asyncio
import string

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
    # (Optional) You can still print device info for debugging, but it's not required
    # for i in range(p.get_device_count()):
    #     print(p.get_device_info_by_index(i))
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                    frames_per_buffer=CHUNK, stream_callback=audio_callback)
    stream.start_stream()
    return stream

def detect_trigger(audio_data):
    if vosk_recognizer.AcceptWaveform(audio_data):
        result = json.loads(vosk_recognizer.Result())
        text = result.get("text", "").lower()
        print(f"[VOSK DETECTED]: {text}")  # Add this line
        return any(w in text for w in TRIGGER_WORDS), text
    return False, ""

def transcribe_whisper(frames):
    audio = np.frombuffer(b''.join(frames), np.int16).astype(np.float32) / 32768.0
    result = whisper_model.transcribe(audio, language="en")
    return result.get("text", "").strip()

def match_command(text):
    for cmd in COMMANDS:
        if cmd.lower() in text.lower():
            return cmd
    # fallback to fuzzy match
    matches = difflib.get_close_matches(text.lower(), [cmd.lower() for cmd in COMMANDS], n=1, cutoff=0.4)
    return matches[0] if matches else None

async def main_loop_websocket(websocket):
    await websocket.accept()
    awaiting_confirmation = False
    pending_command = None
    print("WebSocket accepted")
    await websocket.send_text("Listening started. Say trigger word.")
    print("Message sent")
    
    stream = start_microphone_stream()
    frames = []
    triggered = False
    silence_count = 0
    confirmation_frames = []
    confirmation_silence_count = 0
    collecting_confirmation = False
    confirmation_attempts = 0

    try:
        while True:
            if not awaiting_confirmation:
                if not audio_queue.empty():
                    audio_data = audio_queue.get()
                    frames.append(audio_data)
                    is_triggered, trigger_text = detect_trigger(audio_data)
                    if is_triggered and not triggered:
                        triggered = True
                        await websocket.send_text("Trigger word detected. Please say your command.")
                        frames = []
                        silence_count = 0
                        while not audio_queue.empty():
                            audio_queue.get()
                        await asyncio.sleep(0.5)
                        continue

                    if triggered:
                        silence_count += 1
                        if silence_count > 100:
                            transcript = transcribe_whisper(frames)
                            await websocket.send_text(f"Transcript: {transcript}")
                            command = match_command(transcript)
                            if command:
                                pending_command = command
                                awaiting_confirmation = True
                                await websocket.send_text("Command matched. Are you sure? Say confirm or cancel.")
                            else:
                                await websocket.send_text("No command found. Exiting. Say trigger word again.")
                            triggered = False
                            frames = []
            else:
                # Robust confirmation loop: up to 2 attempts
                for attempt in range(2):
                    if attempt > 0:
                        await websocket.send_text("Did not understand. Please say confirm or cancel.")
                    await asyncio.sleep(2)  # Increased delay to ensure prompt is finished
                    while not audio_queue.empty():
                        audio_queue.get()  # Clear the audio queue after the delay
                    confirmation_frames = []
                    start_time = time.time()
                    duration = 3.5  # seconds
                    while time.time() - start_time < duration:
                        if not audio_queue.empty():
                            audio_data = audio_queue.get()
                            confirmation_frames.append(audio_data)
                        else:
                            await asyncio.sleep(0.01)
                    await websocket.send_text(f"Confirmation frames collected: {len(confirmation_frames)}")
                    transcript = transcribe_whisper(confirmation_frames)
                    await websocket.send_text(f"Transcript: {transcript}")
                    words = transcript.lower().strip().split()
                    if words and words[-1].strip(string.punctuation) == "confirm":
                        await websocket.send_text("Command confirmed. Executing command.")
                        awaiting_confirmation = False
                        pending_command = None
                        break
                    elif words and words[-1].strip(string.punctuation) == "cancel":
                        await websocket.send_text("Command cancelled. Say trigger word again.")
                        awaiting_confirmation = False
                        pending_command = None
                        break
                else:
                    await websocket.send_text("No response detected. Exiting. Say trigger word again.")
                    awaiting_confirmation = False
                    pending_command = None
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
        stream.stop_stream()
        stream.close()