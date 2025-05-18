import subprocess
import os

def convert_to_webp(input_path: str) -> str:
    output_path = input_path + ".webp"
    subprocess.run(["cwebp", "-q", "95", input_path, "-o", output_path], check=True)
    return output_path

def convert_to_avif(input_path: str) -> str:
    output_path = input_path + ".avif"
    subprocess.run(["avifenc", "--min", "30", "--max", "60", input_path, output_path], check=True)
    return output_path
