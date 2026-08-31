# text2audio — render narrative text to audio

Two **fully independent** backends for turning a narrative script into an MP3.
Each is self-contained (own venv, own requirements, own README, own `.env`) and
shares **no code, no dependencies, and no configuration** with the other. Pick
one and run it directly.

| Backend | Directory | Cost | Where it runs | Best for |
|---------|-----------|------|---------------|----------|
| **Azure Neural TTS** | [`azure_tts/`](azure_tts/) | ~$16/1M chars (~$0.168/story) | Anywhere (cloud API) | Fast, best quality, unattended |
| **VoxCPM2** (voice clone) | [`voxcpm/`](voxcpm/) | $0 | Local (MPS/CUDA/CPU) | Free bulk, no spend |

## Quick start

```bash
# Azure (needs AZURE_SPEECH_KEY in azure_tts/.env)
cd azure_tts && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m azure_tts.render -i ../inputs/story.md -o out.mp3

# VoxCPM2 (needs VOXCPM_VENV + VOXCPM_REFERENCE_DIR in voxcpm/.env)
cd ../voxcpm && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m voxcpm.render -i ../inputs/story.md -o out.mp3
```

## Input format

Any plain-text or Markdown file. Both backends accept the same input — a
narrative script with paragraphs separated by blank lines. Example fixture:
[`inputs/story.md`](inputs/story.md).

## Independence guarantee

- No shared `core/`, no shared `config.py`, no shared imports between the two.
- Each backend's `requirements.txt` lists only what it needs.
- Deleting one backend leaves the other fully functional.
