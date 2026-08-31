# Azure Neural TTS — text → audio renderer (self-contained)

A minimal, dependency-light tool that renders a narrative text file to an MP3
using **Azure Neural TTS**. It has no relationship to any other backend — it
stands alone with its own venv, its own requirements, and its own README.

> **Package name:** the module is `azure_tts` (not `azure`) to avoid shadowing
> the `azure` namespace package that the Azure SDK installs.

## Setup

```bash
cd text2audio/azure_tts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your Azure Speech credentials:

```
AZURE_SPEECH_KEY=your_key
AZURE_SPEECH_REGION=eastus
```

> `ffmpeg` is required only for stitching multi-chunk output. On macOS:
> `brew install ffmpeg`. For a single short text (under ~3000 chars) it is not
> needed, because one chunk is written directly.

## Usage

```bash
# Render with auto language detection + default female voice
python -m azure_tts.render -i story.md -o out.mp3

# Explicit voice
python -m azure_tts.render -i story.md -o out.mp3 --voice en-US-AndrewMultilingualNeural

# Explicit language + gender
python -m azure_tts.render -i story.md -o out.mp3 --language zh-CN --gender Male

# Adjust rate
python -m azure_tts.render -i story.md -o out.mp3 --rate 1.1

# List available voices
python -m azure_tts.render --list-voices
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | — | Input text file (`.md`, `.txt`, …) |
| `--output, -o` | — | Output `.mp3` path |
| `--language, -l` | auto | Locale (`en-US`, `zh-CN`, …) |
| `--gender` | Female | `Female` / `Male` (used only if `--voice` omitted) |
| `--voice, -v` | auto | Exact Azure voice name override |
| `--rate` | `0.92` | Speech rate multiplier |
| `--list-voices` | — | Print the voice table and exit |

## How it works

1. Reads the text file.
2. Detects language (`langid`) unless `--language` given.
3. Resolves a voice from the locale + gender (or uses `--voice`).
4. Splits into ≤3000-char chunks (Azure's per-request limit).
5. Synthesizes each chunk to MP3, then stitches with `pydub`/`ffmpeg`.
6. Cleans up temp files.

## Cost

Azure Neural TTS is billed at **$16 / 1M characters** (≈ $0.168 per ~3000-char
story). This is the only cost; there is no compute to rent.

## Files

```
azure_tts/
├── __init__.py
├── render.py        # CLI entry point (python -m azure_tts.render)
├── tts.py           # synthesis + chunking + stitching
├── voices.py        # voice map + locale detection + voice table
├── config.py        # .env loading
├── requirements.txt
├── .env.example
└── README.md
```
