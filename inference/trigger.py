# trigger_inference.py

import os
import queue
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# === CONFIGURATION ===
TRIGGER_WORD = "system"  # Change this to your desired trigger word
SAMPLE_RATE = 16000
MODEL_PATH = "models/vosk-model-en-us-0.22-lgraph"

# === LOAD MODEL ===
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Vosk model not found at {MODEL_PATH}")

print("🔁 Loading Vosk model...")
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)

# === AUDIO STREAM QUEUE ===
audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    """Callback function to collect audio stream chunks."""
    if status:
        print("⚠️", status)
    audio_queue.put(bytes(indata))

# === TRIGGER WORD LISTENER ===
def listen_for_trigger():
    print(f"🎙️ Listening for trigger word: '{TRIGGER_WORD}'...")
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                           channels=1, callback=audio_callback):
        while True:
            data = audio_queue.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower()
                print(f"🗣️ Recognized: {text}")
                if TRIGGER_WORD in text:
                    print(f"✅ Trigger word '{TRIGGER_WORD}' detected!")
                    break

# === MAIN EXECUTION ===
if __name__ == "__main__":
    listen_for_trigger()