# tools

A collection of granular AI tools for various local purposes. Each tool is self-contained in its own directory with independent dependencies and documentation.

## Tools

| Tool | Direction | Description |
|------|-----------|-------------|
| [pdf_jpg](pdf_jpg/) | PDF → image | Convert PDF pages to JPG images using PyMuPDF |
| [text2audio](text2audio/) | text → audio | Render narrative text to audio — two independent backends (Azure Neural TTS, VoxCPM2) |
| [text_clean](text_clean/) | text → text | Clean noisy text + infer speakers via DeepSeek |
| [audio2text](audio2text/) | audio → text | Transcribe audio with speaker diarization via Azure Speech |

## Pipeline composition

The text/audio tools compose into a full bidirectional pipeline:

```
noisy text ──text_clean──▶ clean text ──text2audio──▶ audio
                            (DeepSeek)    (Azure / VoxCPM2)

audio ──audio2text──▶ transcript ──text_clean──▶ clean transcript
       (Azure STT)                (DeepSeek)
```

Each arrow is an independent tool with its own venv, requirements, and README.
No tool imports another.

## Philosophy

- **Granular**: Each tool does one thing well
- **Local-first**: Designed to run on your machine, no deployment needed
- **Self-contained**: Each tool has its own virtualenv, dependencies, and README
- **Composable**: Tools are independent but can be piped together
