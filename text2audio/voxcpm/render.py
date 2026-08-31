"""CLI entry point for the VoxCPM2 backend (self-contained)."""
import argparse
import os
import sys

from . import engine


def main():
    parser = argparse.ArgumentParser(
        prog="voxcpm.render",
        description="Render a narrative text file to MP3 using local VoxCPM2 voice cloning.",
    )
    parser.add_argument("--input", "-i", required=True, help="Input text file (.md, .txt)")
    parser.add_argument("--output", "-o", required=True, help="Output MP3 path")
    parser.add_argument("--gender", default="Female", choices=["Female", "Male", "Unknown"],
                        help="Narrator voice (Unknown → male clip)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)

    print(f"Reading: {args.input}")
    with open(args.input, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        print("Error: input file is empty.")
        sys.exit(1)
    print(f"  Length: {len(text)} chars")

    print(f"Synthesizing audio (VoxCPM2, gender={args.gender})...")
    duration = engine.synthesize(text, args.output, gender=args.gender)
    if duration:
        print(f"✅ Done! Duration: {duration}s → {args.output}")
    else:
        print("❌ Synthesis failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
