"""CLI entry point for audio2text (python -m audio2text.transcribe)."""
import argparse
import os
import sys

from . import config
from . import stt


def main():
    parser = argparse.ArgumentParser(
        prog="audio2text.transcribe",
        description="Transcribe an audio file to a Markdown transcript with speaker diarization.",
    )
    parser.add_argument("--input", "-i", required=True, help="Input audio file (.mp3, .wav)")
    parser.add_argument("--output", "-o", required=True, help="Output transcript file (.md)")
    parser.add_argument("--language", "-l", default="en-US",
                        help="Recognition language locale (default en-US)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)

    speech_key = config.get_env("AZURE_SPEECH_KEY", required=True)
    region = config.get_env("AZURE_SPEECH_REGION", "eastus")

    print(f"Transcribing: {args.input}")
    transcript = stt.transcribe(
        input_path=args.input,
        output_path=args.output,
        speech_key=speech_key,
        region=region,
        language=args.language,
    )
    if transcript:
        print("✅ Done!")
    else:
        print("❌ Transcription failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
