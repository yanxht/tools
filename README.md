# tools

A collection of granular AI tools for various local purposes. Each tool is self-contained in its own directory with independent dependencies and documentation.

## Tools

| Tool | Direction | Description |
|------|-----------|-------------|
| [pdf_jpg](pdf_jpg/) | PDF → image | Convert PDF pages to JPG images using PyMuPDF |
| [ocr_vision](ocr_vision/) | scan → text | Scan (PDF/image) → clean Markdown — local (macOS Vision) + remote (MinerU) backends |
| [text2audio](text2audio/) | text → audio | Render narrative text to audio — two independent backends (Azure Neural TTS, VoxCPM2) |
| [text_clean](text_clean/) | text → text | Clean noisy text + infer speakers via DeepSeek |
| [audio2text](audio2text/) | audio → text | Transcribe audio with speaker diarization via Azure Speech |
| [watermark_remove](watermark_remove/) | image → image | Locate & remove watermarks via DeepSeek Vision + OpenCV inpainting |

## Pipeline composition

The text/audio tools compose into a full bidirectional pipeline:

```
scan (pdf/image) ──ocr_vision──▶ clean Markdown
                   (macOS Vision local / MinerU remote)

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
