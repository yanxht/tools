import argparse
import sys
import os

from . import config
from .core import tts, stt, llm


def cmd_text2audio(args):
    """Text → Audio pipeline."""
    # Handle --list-voices
    if args.list_voices:
        tts.print_voice_table()
        return

    # Validate inputs
    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    if args.ai and not args.prompt:
        print("Error: --ai requires --prompt <instruction_file>")
        sys.exit(1)

    if args.prompt and not args.ai:
        print("Warning: --prompt is ignored without --ai flag")

    # Check required keys
    speech_key = config.get_env("AZURE_SPEECH_KEY", required=True)
    region = config.get_env("AZURE_SPEECH_REGION", "eastus")

    # Read input text
    print(f"Reading: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.strip():
        print("Error: Input file is empty.")
        sys.exit(1)

    print(f"  Length: {len(text)} chars")

    # Optional: AI cleanup
    if args.ai:
        deepseek_key = config.get_env("DEEPSEEK_API_KEY", required=True)
        print(f"Applying AI processing: {args.prompt}")
        text = llm.process_text(text, args.prompt, deepseek_key)
        print(f"  Processed length: {len(text)} chars")

    # Optional: multi-voice speaker inference
    speaker_voices = None
    if args.multi_voice:
        deepseek_key = config.get_env("DEEPSEEK_API_KEY", required=True)
        print("Inferring speakers...")
        result = llm.infer_speakers(text, deepseek_key)
        speakers = result.get("speakers", [])
        text = result.get("labeled_text", text)

        locale = args.language or tts.detect_locale(text)
        speaker_voices = {}
        for s in speakers:
            sid = s["id"]
            gender = s.get("gender", "Female")
            speaker_voices[sid] = tts.resolve_voice(locale, gender)
            print(f"  {sid} ({s.get('description', '')}): {speaker_voices[sid]}")

    # Synthesize
    print("Synthesizing audio...")
    ok = tts.synthesize(
        text=text,
        output_path=args.output,
        speech_key=speech_key,
        region=region,
        voice_name=args.voice,
        language=args.language,
        rate=args.rate,
        multi_voice=args.multi_voice,
        speaker_voices=speaker_voices,
    )

    if ok:
        print("✅ Done!")
    else:
        print("❌ Synthesis failed.")
        sys.exit(1)


def cmd_audio2text(args):
    """Audio → Text pipeline."""
    # Validate
    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    if args.ai and not args.prompt:
        print("Error: --ai requires --prompt <instruction_file>")
        sys.exit(1)

    speech_key = config.get_env("AZURE_SPEECH_KEY", required=True)
    region = config.get_env("AZURE_SPEECH_REGION", "eastus")

    # Transcribe
    print(f"Transcribing: {args.input}")
    transcript = stt.transcribe(
        input_path=args.input,
        output_path=args.output,
        speech_key=speech_key,
        region=region,
        language=args.language,
    )

    if not transcript:
        print("❌ Transcription failed.")
        sys.exit(1)

    # Optional: AI post-processing
    if args.ai:
        deepseek_key = config.get_env("DEEPSEEK_API_KEY", required=True)
        print(f"Applying AI processing: {args.prompt}")
        processed = llm.process_text(transcript, args.prompt, deepseek_key)

        # Write AI output alongside the raw transcript
        base, ext = os.path.splitext(args.output)
        ai_output_path = base + "_ai" + ext
        with open(ai_output_path, "w", encoding="utf-8") as f:
            f.write(processed)
        print(f"  AI output: {ai_output_path}")

    print("✅ Done!")


def main():
    parser = argparse.ArgumentParser(
        prog="text_audio",
        description="Bidirectional text ↔ audio conversion tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- text2audio ---
    p_t2a = subparsers.add_parser("text2audio", help="Convert text file to audio (MP3)")
    p_t2a.add_argument("--input", "-i", required=False, help="Path to input text file (.md, .txt)")
    p_t2a.add_argument("--output", "-o", required=False, help="Path to output audio file (.mp3)")
    p_t2a.add_argument("--language", "-l", default=None, help="Language locale (e.g., en-US, zh-CN). Auto-detected if omitted.")
    p_t2a.add_argument("--voice", "-v", default=None, help="Azure TTS voice name override (use --list-voices to see options)")
    p_t2a.add_argument("--rate", default="0.92", help="Speech rate (default: 0.92)")
    p_t2a.add_argument("--ai", action="store_true", help="Enable AI text processing before synthesis")
    p_t2a.add_argument("--prompt", "-p", default=None, help="Path to instruction file for AI processing (required with --ai)")
    p_t2a.add_argument("--multi-voice", action="store_true", help="Infer speakers and use different voices")
    p_t2a.add_argument("--list-voices", action="store_true", help="Print available voices and exit")
    p_t2a.set_defaults(func=cmd_text2audio)

    # --- audio2text ---
    p_a2t = subparsers.add_parser("audio2text", help="Transcribe audio file to text (Markdown)")
    p_a2t.add_argument("--input", "-i", required=True, help="Path to input audio file (.mp3, .wav)")
    p_a2t.add_argument("--output", "-o", required=True, help="Path to output transcript file (.md)")
    p_a2t.add_argument("--language", "-l", default="en-US", help="Recognition language locale (default: en-US)")
    p_a2t.add_argument("--ai", action="store_true", help="Enable AI post-processing of transcript")
    p_a2t.add_argument("--prompt", "-p", default=None, help="Path to instruction file for AI processing (required with --ai)")
    p_a2t.set_defaults(func=cmd_audio2text)

    args = parser.parse_args()

    # For text2audio: --input and --output are required unless --list-voices
    if args.command == "text2audio" and not args.list_voices:
        if not args.input or not args.output:
            p_t2a.error("--input and --output are required")

    args.func(args)
