"""CLI entry point for the Azure Neural TTS backend (self-contained)."""
import argparse
import os
import sys

from . import config
from . import tts, voices


def main():
    parser = argparse.ArgumentParser(
        prog="azure_tts.render",
        description="Render a narrative text file to MP3 using Azure Neural TTS.",
    )
    parser.add_argument("--input", "-i", help="Input text file (.md, .txt)")
    parser.add_argument("--output", "-o", help="Output MP3 path")
    parser.add_argument("--language", "-l", default=None,
                        help="Locale (e.g. en-US, zh-CN). Auto-detected if omitted.")
    parser.add_argument("--gender", default="Female", choices=["Female", "Male"],
                        help="Voice gender (used only if --voice omitted)")
    parser.add_argument("--voice", "-v", default=None,
                        help="Exact Azure voice name override")
    parser.add_argument("--rate", default="0.92", help="Speech rate (default 0.92)")
    parser.add_argument("--list-voices", action="store_true",
                        help="Print the voice table and exit")
    args = parser.parse_args()

    if args.list_voices:
        voices.print_voice_table()
        return

    if not args.input or not args.output:
        parser.error("--input and --output are required (or use --list-voices)")
    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)

    speech_key = config.get_env("AZURE_SPEECH_KEY", required=True)
    region = config.get_env("AZURE_SPEECH_REGION", "eastus")

    print(f"Reading: {args.input}")
    with open(args.input, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        print("Error: input file is empty.")
        sys.exit(1)
    print(f"  Length: {len(text)} chars")

    print("Synthesizing audio...")
    ok = tts.synthesize(
        text=text,
        output_path=args.output,
        speech_key=speech_key,
        region=region,
        voice_name=args.voice,
        language=args.language,
        gender=args.gender,
        rate=args.rate,
    )
    if ok:
        print("✅ Done!")
    else:
        print("❌ Synthesis failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
