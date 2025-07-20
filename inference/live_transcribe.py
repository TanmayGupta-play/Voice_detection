import whisper
import pyaudio
import wave
import os
import time
import json
import difflib
import queue
from vosk import Model, KaldiRecognizer

# === Load Command Data ===
base_dir = os.path.dirname(os.path.dirname(__file__))  # parent of /inference
commands_path = os.path.join(base_dir, "utils", "commands.json")
with open(commands_path, "r") as f:
    COMMANDS = json.load(f)

# === Whisper ASR Model ===
whisper_model = whisper.load_model("medium")

# === Vosk Trigger Word Detection Setup ===
vosk_model_path = os.path.join(base_dir, "models", "vosk")  # e.g., models/vosk/
vosk_model = Model(vosk_model_path)
TRIGGER_WORDS = ["system"]
TRIGGER_RECOGNIZER = KaldiRecognizer(vosk_model, 16000)
TRIGGER_RECOGNIZER.SetWords(True)

# === Audio Config ===
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 5

audio_interface = pyaudio.PyAudio()

# === Record Short Snippet for Whisper ===
def record_temp_audio(filename="temp_stream.wav", duration=RECORD_SECONDS):
    stream = audio_interface.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []
    print("🎧 Listening for command...")
    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio_interface.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    return filename

# === Match to Valid Command ===
def match_command(text):
    matches = difflib.get_close_matches(text.strip().lower(), [cmd.lower() for cmd in COMMANDS], n=1, cutoff=0.6)
    return matches[0] if matches else None

# === Confirm Command (Confirm / Cancel) ===
def confirm_action():
    print("🗣️ Say 'Confirm' or 'Cancel'")
    file = record_temp_audio("confirm.wav", duration=3)
    result = whisper_model.transcribe(file)
    confirm_text = result["text"].strip().lower()
    print(f"🔊 You said: {confirm_text}")
    if "confirm" in confirm_text:
        return True
    elif "cancel" in confirm_text or "abort" in confirm_text:
        return False
    return None

# === Trigger Word Detection ===
def listen_for_trigger():
    stream = audio_interface.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print("🎙️ Awaiting trigger word... (say 'system')")
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        if TRIGGER_RECOGNIZER.AcceptWaveform(data):
            result = json.loads(TRIGGER_RECOGNIZER.Result())
            text = result.get("text", "").lower()
            if any(word in text for word in TRIGGER_WORDS):
                print("🟢 Trigger word detected!")
                stream.stop_stream()
                stream.close()
                return

# === Main Control Loop ===
def main_loop():
    try:
        print("🛫 Cockpit Command System LIVE (Press Ctrl+C to stop)")
        while True:
            listen_for_trigger()
            audio_file = record_temp_audio()
            result = whisper_model.transcribe(audio_file)
            text = result["text"].strip()
            print(f"📜 Transcript: {text}")

            command = match_command(text)
            if command:
                print(f"🤖 AI: You said '{command}'. Confirm?")
                decision = confirm_action()
                if decision is True:
                    print(f"✅ Command executed: {command}")
                elif decision is False:
                    print(f"❌ Command aborted.")
                else:
                    print(f"⚠️ No decision made. Ignoring.")
            else:
                print("🚫 Not a valid cockpit command.")
            print("-" * 40)

    except KeyboardInterrupt:
        print("\n🛑 Exiting...")
        audio_interface.terminate()

if __name__ == "__main__":
    main_loop()