import queue
import threading
import sounddevice as sd
import numpy as np
import whisper
import os
import time
import json
from vosk import Model as VoskModel, KaldiRecognizer
import pyttsx3
import wave

# ========== Config ==========
TRIGGER_WORDS = ["system"]
CONFIRM_WORDS = ["confirm", "cancel"]
COMMANDS_FILE = "commands.json"
SAMPLE_RATE = 16000
RECORD_DURATION = 4  # seconds
AUDIO_FILE = "temp.wav"
VOSK_PATH = "vosk-model-small-en-us-0.15"

# ========== Load Models ==========
whisper_model = whisper.load_model("base")
vosk_model = VoskModel(VOSK_PATH)
rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)

# ========== TTS ==========
speaker = pyttsx3.init()
def speak(text):
    speaker.say(text)
    speaker.runAndWait()

# ========== Command Matching ==========
def match_command(text):
    with open(COMMANDS_FILE) as f:
        valid_commands = json.load(f)
    for cmd in valid_commands:
        if cmd.lower() in text.lower():
            return cmd
    return None

# ========== Audio Functions ==========
def record_temp_audio(duration=RECORD_DURATION):
    print("🎙️ Recording command...")
    recording = sd.rec(int(SAMPLE_RATE * duration), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
    sd.wait()
    with wave.open(AUDIO_FILE, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(recording.tobytes())
    return AUDIO_FILE

def listen_for_keyword(keywords):
    q = queue.Queue()
    def callback(indata, frames, time, status):
        if status:
            print(status)
        q.put(bytes(indata))

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                           channels=1, callback=callback):
        print("🎧 Listening for trigger word...")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                word = result.get("text", "")
                if any(w in word.lower() for w in keywords):
                    print(f"🚀 Detected: {word}")
                    break

# ========== Confirm / Cancel ==========
def confirm_action():
    speak("Please confirm or cancel.")
    print("🎧 Listening for confirmation...")
    q = queue.Queue()
    def callback(indata, frames, time, status):
        if status:
            print(status)
        q.put(bytes(indata))

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                           channels=1, callback=callback):
        rec_conf = KaldiRecognizer(vosk_model, SAMPLE_RATE)
        start_time = time.time()
        while time.time() - start_time < 5:  # 5 sec window
            data = q.get()
            if rec_conf.AcceptWaveform(data):
                result = json.loads(rec_conf.Result())
                word = result.get("text", "")
                print(f"🔁 Confirm heard: {word}")
                if "confirm" in word:
                    return True
                elif "cancel" in word:
                    return False
        return None

# ========== Main Inference Loop ==========
def main_loop():
    try:
        print("🛫 Cockpit Command System LIVE (Press Ctrl+C to stop)")
        while True:
            # Step 1: Trigger
            listen_for_keyword(TRIGGER_WORDS)

            # Step 2: Record Command
            audio_path = record_temp_audio()
            result = whisper_model.transcribe(audio_path)
            transcript = result["text"].strip()
            print(f"📜 Transcript: {transcript}")

            # Step 3: Match
            command = match_command(transcript)
            if command:
                speak(f"You said {command}. Confirm or cancel?")
                decision = confirm_action()
                if decision is True:
                    print(f"✅ Confirmed: {command}")
                    speak(f"Confirmed. Executing {command}.")
                    # TODO: trigger real action
                elif decision is False:
                    print("❌ Cancelled")
                    speak("Command cancelled.")
                else:
                    print("⚠️ No confirmation received")
                    speak("No decision made. Ignoring command.")
            else:
                print("🚫 Invalid command")
                speak("Command not recognized.")
            print("-" * 50)
    except KeyboardInterrupt:
        print("\n🛑 Stopped")

if __name__ == "__main__":
    main_loop()