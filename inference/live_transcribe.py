import whisper
import pyaudio
import wave
import os
import time
import json
import difflib
# Dynamically build absolute path to commands.json
base_dir = os.path.dirname(os.path.dirname(__file__))  # parent of /inference
commands_path = os.path.join(base_dir, "utils", "commands.json")

# Load commands
with open(commands_path, "r") as f:
    COMMANDS = json.load(f)

# Load Whisper model (use "medium" or "large" for cockpit-level noise)
model = whisper.load_model("medium")

# Mic recording config
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 5

# Setup PyAudio
audio = pyaudio.PyAudio()

# Function to record mic input and save as .wav
def record_temp_audio(filename="temp_stream.wav", duration=RECORD_SECONDS):
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []

    print("🎧 Listening for command...")
    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()

    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    return filename

# Match transcribed text to known command
def match_command(text):
    matches = difflib.get_close_matches(text.strip().lower(), [cmd.lower() for cmd in COMMANDS], n=1, cutoff=0.6)
    return matches[0] if matches else None

# Record confirmation (Confirm / Cancel)
def confirm_action():
    print("🗣️ Say 'Confirm' or 'Cancel'")
    file = record_temp_audio("confirm.wav", duration=3)
    result = model.transcribe(file)
    confirm_text = result["text"].strip().lower()
    print(f"🔊 You said: {confirm_text}")
    if "confirm" in confirm_text:
        return True
    elif "cancel" in confirm_text or "abort" in confirm_text:
        return False
    return None

# Main loop for live streaming
def main_loop():
    try:
        print("🛫 Cockpit Command System LIVE (Ctrl+C to stop)")
        while True:
            audio_file = record_temp_audio()
            result = model.transcribe(audio_file)
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
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Exiting live stream...")
        audio.terminate()

if __name__ == "__main__":
    main_loop()
