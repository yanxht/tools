"""CLI: clean noisy text via DeepSeek (python -m text_clean.clean)."""
import argparse
import os
import sys

from . import config
from . import llm

DEFAULT_PROMPT = os.path.join(os.path.dirname(__file__), "prompts", "default_clean.md")


def main():
    parser = argparse.ArgumentParser(
        prog="text_clean.clean",
        description="Clean noisy narrative text via DeepSeek (strip noise, infer gender).",
    )
    parser.add_argument("--input", "-i", required=True, help="Input text file")
    parser.add_argument("--output", "-o", required=True, help="Output cleaned text file")
    parser.add_argument("--prompt", "-p", default=DEFAULT_PROMPT,
                        help="Instruction file (default: prompts/default_clean.md)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)
    if not os.path.isfile(args.prompt):
        print(f"Error: prompt file not found: {args.prompt}")
        sys.exit(1)

    api_key = config.get_env("DEEPSEEK_API_KEY", required=True)

    print(f"Reading: {args.input}")
    with open(args.input, encoding="utf-8") as f:
        text = f.read()
    print(f"  Length: {len(text)} chars")

    print(f"Cleaning with: {args.prompt}")
    cleaned = llm.process_text(text, args.prompt, api_key)
    print(f"  Cleaned length: {len(cleaned)} chars")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(cleaned)
    print(f"✅ Done! → {args.output}")


if __name__ == "__main__":
    main()
