# audio2text — Azure Speech transcription with speaker diarization

Self-contained tool that transcribes an audio file to a Markdown transcript
using **Azure Speech** conversation transcription (multi-speaker diarization).
No dependency on any other tool.

## Setup

```bash
cd audio2text
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`:

```
AZURE_SPEECH_KEY=your_key
AZURE_SPEECH_REGION=eastus
```

> `ffmpeg` is required to decode audio to PCM: `brew install ffmpeg`.

## Usage

```bash
# Transcribe with speaker diarization (default English)
python -m audio2text.transcribe -i meeting.mp3 -o transcript.md

# Non-English
python -m audio2text.transcribe -i interview.wav -o transcript.md --language zh-CN
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | — | Input audio file (`.mp3`, `.wav`, …) |
| `--output, -o` | — | Output transcript file (`.md`) |
| `--language, -l` | `en-US` | Recognition language locale |

## Output format

```markdown
# Transcript

- **Source:** meeting.mp3
- **Language:** en-US
- **Speakers detected:** 2
- **Duration:** 105.0s

---

[Speaker 1]: Hello everyone.
[Speaker 2]: Thanks for joining.
```

## How it works

1. Decodes the audio to 16 kHz mono 16-bit PCM via `pydub`/`ffmpeg`.
2. Streams PCM frames to Azure `ConversationTranscriber` (real-time diarization).
3. Collects `[Speaker N]: text` segments, normalizes speaker IDs.
4. Writes a Markdown transcript with metadata header.

## Files

```
audio2text/
├── __init__.py
├── transcribe.py    # CLI entry point (python -m audio2text.transcribe)
├── stt.py           # Azure ConversationTranscriber + stream + diarization
├── config.py        # .env loading
├── requirements.txt
├── .env.example
└── README.md
```
