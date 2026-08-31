"""CLI: label speakers in dialogue via DeepSeek (python -m text_clean.multi_voice)."""
import argparse
import json
import os
import sys

from . import config
from . import llm


def main():
    parser = argparse.ArgumentParser(
        prog="text_clean.multi_voice",
        description="Infer distinct speakers in dialogue and label each line.",
    )
    parser.add_argument("--input", "-i", required=True, help="Input text file")
    parser.add_argument("--output", "-o", required=True, help="Output labeled text file")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)

    api_key = config.get_env("DEEPSEEK_API_KEY", required=True)

    print(f"Reading: {args.input}")
    with open(args.input, encoding="utf-8") as f:
        text = f.read()

    print("Inferring speakers...")
    result = llm.infer_speakers(text, api_key)
    speakers = result.get("speakers", [])
    labeled_text = result.get("labeled_text", text)

    for s in speakers:
        print(f"  {s['id']} ({s.get('gender', '?')}): {s.get('description', '')}")

    # Write the labeled text
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(labeled_text)

    # Write the JSON metadata alongside
    json_path = args.output + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ Done! → {args.output} (+ {json_path})")


if __name__ == "__main__":
    main()
