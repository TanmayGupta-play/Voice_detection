import os
import whisper

# Define your directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(BASE_DIR, "data", "audio")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")

# Load Whisper model (choose: tiny, base, small, medium, large)
model = whisper.load_model("medium")  # or "small" for better accuracy

# Ensure output folder exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

for file in os.listdir(AUDIO_DIR):
    if file.endswith(".wav"):
        input_path = os.path.join(AUDIO_DIR, file)
        output_path = os.path.join(OUTPUT_DIR, file.replace(".wav", ".txt"))

        print(f"🎙️ Transcribing: {file}")
        result = model.transcribe(input_path)
        transcript = result["text"].strip()

        # Save transcription to output folder
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcript)

        print(f"✅ Saved to: {output_path}")
