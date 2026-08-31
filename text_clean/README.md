# text_clean — DeepSeek text cleanup

Self-contained tool for cleaning noisy narrative text (Reddit posts, interview
transcripts, etc.) using the DeepSeek LLM. Two capabilities:

1. **Clean** — strip noise (HTML, Reddit meta, filler words) and infer narrator gender.
2. **Multi-voice** — infer distinct speakers from dialogue and label each line.

No dependency on any other tool — it stands alone with its own venv, its own
requirements, and its own README.

## Setup

```bash
cd text_clean
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`:

```
DEEPSEEK_API_KEY=your_key
```

## Usage

### clean — de-noise a narrative

```bash
# Clean with the default prompt (Reddit noise + filler removal + gender inference)
python -m text_clean.clean -i noisy.md -o clean.md

# Clean with a custom instruction file
python -m text_clean.clean -i noisy.md -o clean.md --prompt my_rules.md
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | — | Input text file |
| `--output, -o` | — | Output cleaned text file |
| `--prompt, -p` | `prompts/default_clean.md` | Instruction file for the LLM |

### multi-voice — label speakers in dialogue

```bash
python -m text_clean.multi_voice -i dialogue.md -o labeled.md
```

Outputs a JSON file `labeled.md.json` with `speakers[]` (id/gender/description)
and `labeled_text`, plus a human-readable `labeled.md` with `[Speaker N]:` labels.

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | — | Input text file |
| `--output, -o` | — | Output labeled text file |

## Files

```
text_clean/
├── __init__.py
├── clean.py         # CLI: python -m text_clean.clean
├── multi_voice.py   # CLI: python -m text_clean.multi_voice
├── llm.py           # DeepSeek client + process_text + infer_speakers
├── config.py        # .env loading
├── prompts/
│   └── default_clean.md
├── requirements.txt
├── .env.example
└── README.md
```
