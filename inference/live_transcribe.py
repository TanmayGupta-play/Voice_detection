import whisper
import pyaudio
import wave
import os
import time
import json
import difflib
import queue
import pyttsx3
from vosk import Model, KaldiRecognizer

# === Load Command Data ===
base_dir = os.path.dirname(os.path.dirname(__file__))  # parent of /inference
commands_path = os.path.join(base_dir, "utils", "commands.json")
with open(commands_path, "r") as f:
    COMMANDS = json.load(f)

# === Whisper ASR Model ===
whisper_model = whisper.load_model("base")  # Use base for speed during testing

# === Vosk Trigger Word Detection Setup ===
vosk_model_path = os.path.join(base_dir, "models", "vosk")
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

# === Text-to-Speech ===
tts_engine = pyttsx3.init()
def speak(text):
    print(f"🔈 Speaking: {text}")
    tts_engine.say(text)
    tts_engine.runAndWait()

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
    speak("Say confirm or cancel.")
    print("🗣️ Say 'Confirm' or 'Cancel'")
    file = record_temp_audio("confirm.wav", duration=3)
    try:
        result = whisper_model.transcribe(file)
        confirm_text = result.get("text", "").strip().lower()
        print(f"🔊 You said: {confirm_text}")
        if "confirm" in confirm_text:
            return True
        elif "cancel" in confirm_text or "abort" in confirm_text:
            return False
    except Exception as e:
        print(f"❌ Confirmation transcription failed: {e}")
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
            try:
                result = whisper_model.transcribe(audio_file)
                text = result.get("text", "").strip()
            except Exception as e:
                print(f"❌ Transcription failed: {e}")
                continue

            print(f"📜 Transcript: {text}")
            command = match_command(text)
            if command:
                prompt = f"You said {command}. Confirm?"
                print(f"🤖 AI: {prompt}")
                speak(prompt)
                decision = confirm_action()
                if decision is True:
                    msg = f"✅ Command executed: {command}"
                    print(msg)
                    speak(msg)
                elif decision is False:
                    msg = f"❌ Command aborted."
                    print(msg)
                    speak(msg)
                else:
                    msg = f"⚠️ No decision made. Ignoring."
                    print(msg)
                    speak(msg)
            else:
                msg = "🚫 Not a valid cockpit command."
                print(msg)
                speak(msg)
            print("-" * 40)

    except KeyboardInterrupt:
        print("\n🛑 Exiting...")
        audio_interface.terminate()

if __name__ == "__main__":
    main_loop()