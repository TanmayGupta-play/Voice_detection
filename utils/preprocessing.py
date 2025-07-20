import os
import ffmpeg

# Dynamically get the project root directory (1 level above /utils/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define input and output directories relative to project root
INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "audio")

def convert_all_to_wav(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR, sample_rate=16000):
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    files = os.listdir(input_dir)
    if not files:
        print(f"[⚠️] No files found in '{input_dir}'")
        return

    for file in files:
        if file.endswith((".wav", ".mp3", ".mp4", ".m4a")):
            input_path = os.path.join(input_dir, file)
            base_name = os.path.splitext(file)[0]
            output_path = os.path.join(output_dir, base_name + "_converted.wav")

            try:
                print(f"[🔁] Converting {file} → {output_path}")
                (
                    ffmpeg
                    .input(input_path)
                    .output(output_path, format='wav', ar=sample_rate, ac=1)
                    .overwrite_output()
                    .run(quiet=True)
                )
                print(f"[✅] Saved: {output_path}")
            except ffmpeg.Error as e:
                print(f"[❌] Failed to convert {file}: {e.stderr.decode()}")

if __name__ == "__main__":
    convert_all_to_wav()
