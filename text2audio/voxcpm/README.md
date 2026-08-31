# VoxCPM2 — text → audio renderer (self-contained)

A local, **zero-cost** text → audio renderer using the open-source
[VoxCPM2](https://github.com/OpenBMB/VoxCPM) voice-cloning model. It has no
relationship to any other backend — it stands alone with its own venv, its own
requirements, and its own README.

## How it works

VoxCPM2 clones a reference voice (a short WAV clip) and synthesizes your text in
that voice. This backend runs **entirely locally** — no API calls, no cloud cost.
It auto-selects the fastest device: **CUDA → Apple Silicon MPS → CPU**.

## Prerequisites

1. **A Python 3.12 venv with VoxCPM2 + PyTorch installed** (this is heavy, so it
   lives OUTSIDE this tool). By default the tool looks for
   `~/envs/voiceforge/bin/python`. Set `VOXCPM_VENV` to override.
2. **Reference voice clips** (`.wav`). By default the tool looks in
   `VOXCPM_REFERENCE_DIR` (default `~/voxcpm_data/`) for `male_reference.wav` and
   `female_reference.wav`. Set `VOXCPM_REFERENCE_DIR` to override.
3. `ffmpeg` on PATH (for MP3 export): `brew install ffmpeg`.

## Setup

```bash
cd text2audio/voxcpm
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the two paths:

```
VOXCPM_VENV=/Users/you/envs/voiceforge/bin/python
VOXCPM_REFERENCE_DIR=/Users/you/voxcpm_data
```

> The `.venv` here is only for the thin CLI wrapper (`python-dotenv`). The heavy
> VoxCPM2/PyTorch work happens in the separate `VOXCPM_VENV` interpreter.

## Usage

```bash
# Default: female narrator voice
python -m voxcpm.render -i story.md -o out.mp3

# Male narrator
python -m voxcpm.render -i story.md -o out.mp3 --gender Male
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | — | Input text file (`.md`, `.txt`, …) |
| `--output, -o` | — | Output `.mp3` path |
| `--gender` | Female | `Female` / `Male` / `Unknown` (Unknown → male clip) |

## Performance

| Device | RTF | Note |
|--------|-----|------|
| CUDA (NVIDIA GPU) | ~0.4× | Fastest — needs a GPU box |
| Apple Silicon MPS | ~3–4× | ~9 min per ~3k-char story |
| CPU | slower | Fallback only |

## Cost

**$0.** No API calls. The only inputs are your reference clips and local compute.

## Files

```
voxcpm/
├── __init__.py
├── render.py        # CLI entry point (python -m voxcpm.render)
├── engine.py        # spawns the VoxCPM2 worker + collects the result
├── worker.py        # the VoxCPM2 synthesis script (runs in VOXCPM_VENV)
├── config.py        # .env loading
├── requirements.txt
├── .env.example
└── README.md
```
