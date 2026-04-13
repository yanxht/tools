# text_audio

Bidirectional text ↔ audio conversion tool. Converts local text files to speech (MP3) and transcribes audio files to text (Markdown) with optional AI processing.

## Setup

```bash
cd text_audio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg  # required for audio processing
```

Copy `.env.example` to `.env` and fill in your keys:

```
AZURE_SPEECH_KEY=your_key
AZURE_SPEECH_REGION=eastus
DEEPSEEK_API_KEY=your_key    # only needed if using --ai or --multi-voice
```

## Usage

### text2audio — Convert text to speech

```bash
# Basic: auto-detect language, default female voice
python -m text_audio text2audio -i input.md -o output.mp3

# With AI cleanup (requires instruction file)
python -m text_audio text2audio -i raw_post.md -o clean.mp3 --ai --prompt prompts/default_clean.md

# Multi-voice: LLM infers speakers from dialogue
python -m text_audio text2audio -i dialogue.md -o voices.mp3 --multi-voice

# Explicit language and voice
python -m text_audio text2audio -i chinese.md -o out.mp3 --voice zh-CN-YunyiMultilingualNeural

# Faster rate
python -m text_audio text2audio -i input.md -o fast.mp3 --rate 1.2

# List available voices
python -m text_audio text2audio --list-voices
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--input, -i` | Yes* | — | Input text file (.md, .txt, etc.) |
| `--output, -o` | Yes* | — | Output audio file (.mp3) |
| `--language, -l` | No | auto-detect | Language locale (e.g., `en-US`, `zh-CN`) |
| `--voice, -v` | No | from voice map | Azure TTS voice name override |
| `--rate` | No | `0.92` | Speech rate |
| `--ai` | No | off | Apply AI text processing before synthesis |
| `--prompt, -p` | If `--ai` | — | Path to instruction file for AI |
| `--multi-voice` | No | off | Infer speakers, assign different voices |
| `--list-voices` | No | — | Print voice table and exit |

*Not required when using `--list-voices`

### audio2text — Transcribe audio to text

```bash
# Basic transcription with speaker diarization
python -m text_audio audio2text -i meeting.mp3 -o transcript.md

# With AI post-processing (e.g., summarize)
python -m text_audio audio2text -i interview.mp3 -o transcript.md \
    --ai --prompt my_summary_instructions.md

# Non-English audio
python -m text_audio audio2text -i lecture.mp3 -o transcript.md --language zh-CN
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--input, -i` | Yes | — | Input audio file (.mp3, .wav) |
| `--output, -o` | Yes | — | Output transcript file (.md) |
| `--language, -l` | No | `en-US` | Recognition language locale |
| `--ai` | No | off | Apply AI post-processing to transcript |
| `--prompt, -p` | If `--ai` | — | Path to instruction file for AI |

When `--ai` is used, two files are produced:
- `output.md` — raw transcript with speaker labels
- `output_ai.md` — AI-processed version

## Voice Reference

| Language | Locale | Female | Male |
|----------|--------|--------|------|
| English (US) | `en-US` | en-US-AvaMultilingualNeural | en-US-AndrewMultilingualNeural |
| English (UK) | `en-GB` | en-GB-SoniaNeural | en-GB-RyanNeural |
| Chinese (Mandarin) | `zh-CN` | zh-CN-XiaoxiaoMultilingualNeural | zh-CN-YunyiMultilingualNeural |
| Chinese (Taiwanese) | `zh-TW` | zh-TW-HsiaoChenNeural | zh-TW-YunJheNeural |
| Japanese | `ja-JP` | ja-JP-NanamiNeural | ja-JP-KeitaNeural |
| Korean | `ko-KR` | ko-KR-SunHiNeural | ko-KR-InJoonNeural |
| Spanish | `es-ES` | es-ES-ElviraNeural | es-ES-AlvaroNeural |
| French | `fr-FR` | fr-FR-DeniseNeural | fr-FR-HenriNeural |
| German | `de-DE` | de-DE-KatjaNeural | de-DE-ConradNeural |

Multilingual voices (Ava, Andrew, Xiaoxiao, Yunyi) handle mixed-language text naturally — e.g., Chinese text with embedded English book titles.

## Architecture

```
text_audio/
├── __main__.py          # entry point
├── cli.py               # argparse CLI
├── config.py            # .env loading
├── requirements.txt
├── prompts/
│   ├── default_clean.md       # default text cleanup instructions
│   └── default_transcribe.md  # default transcript cleanup instructions
└── core/
    ├── llm.py           # DeepSeek: apply instruction files
    ├── chunker.py       # sentence-aware text splitting + checkpointing
    ├── tts.py           # Azure TTS synthesis + stitching
    └── stt.py           # Azure STT conversation transcription
```

### Key Design Decisions

- **Sentence-boundary chunking**: Splits at sentence ends (not mid-word) with clause-level and word-level fallbacks. Max 3000 chars per chunk (Azure TTS limit).
- **Checkpoint/resume**: Each synthesized chunk is saved to disk. If synthesis fails at chunk N, re-running resumes from chunk N.
- **Multi-voice**: LLM (DeepSeek) infers speakers from dialogue markers and assigns gendered voices from the voice map.
- **STT diarization**: Azure ConversationTranscriber identifies individual speakers. Audio is decoded to PCM via pydub and streamed frame-by-frame.
- **No text limit**: Handles arbitrarily long input. Chunker + checkpointing makes this reliable.

## Dependencies

- Python 3.12+
- ffmpeg (`brew install ffmpeg`)
- Azure Speech SDK (TTS + STT)
- DeepSeek API (optional, for `--ai` and `--multi-voice`)
