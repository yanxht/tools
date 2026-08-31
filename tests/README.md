# Tests

Shared test fixtures and rendered results for the text/audio tools. Inputs are
committed so results are reproducible; outputs demonstrate each tool works.

## Test Matrix

### text2audio (text → audio)

| # | Scenario | Input | Flags | Output | Result |
|---|----------|-------|-------|--------|--------|
| 1 | Azure, English auto-detect | `inputs/story.md` | — | `outputs/azure_story.mp3` | ✅ 83.7s, `en-US-Ava` |
| 2 | Azure, Chinese auto-detect | `inputs/chinese_text.md` | — | `outputs/chinese_auto.mp3` | ✅ `zh-CN-Xiaoxiao` |
| 3 | Azure, explicit male + rate | `inputs/chinese_text.md` | `--voice zh-CN-YunyiMultilingualNeural --rate 1.2` | `outputs/chinese_male.mp3` | ✅ |
| 4 | VoxCPM2, English female | `inputs/story.md` | — | `outputs/voxcpm_story.mp3` | ✅ 72.8s, MPS |

### text_clean (text → text)

| # | Scenario | Input | Flags | Output | Result |
|---|----------|-------|-------|--------|--------|
| 5 | Clean noisy Reddit post | `inputs/noisy_story.md` | — | `outputs/clean_noisy.md` | ✅ 6841→6521 chars |
| 6 | Multi-voice speaker inference | `inputs/dialogue_story.md` | — | `outputs/dialogue_labeled.md` (+ `.json`) | ✅ 5 speakers |

### audio2text (audio → text)

| # | Scenario | Input | Flags | Output | Result |
|---|----------|-------|-------|--------|--------|
| 7 | Chinese multi-speaker diarization | `inputs/multi_speaker.WAV` | `--language zh-CN` | `outputs/transcript_multi_speaker.md` | ✅ 2 speakers, 6 segments |

## Reproducing

```bash
cd tools

# text2audio (Azure)
text2audio/azure_tts/.venv/bin/python -m azure_tts.render -i tests/inputs/story.md -o tests/outputs/azure_story.mp3

# text2audio (VoxCPM2)
text2audio/voxcpm/.venv/bin/python -m voxcpm.render -i tests/inputs/story.md -o tests/outputs/voxcpm_story.mp3

# text_clean
text_clean/.venv/bin/python -m text_clean.clean -i tests/inputs/noisy_story.md -o tests/outputs/clean_noisy.md
text_clean/.venv/bin/python -m text_clean.multi_voice -i tests/inputs/dialogue_story.md -o tests/outputs/dialogue_labeled.md

# audio2text
audio2text/.venv/bin/python -m audio2text.transcribe -i tests/inputs/multi_speaker.WAV -o tests/outputs/transcript_multi_speaker.md --language zh-CN
```

> Run `python -m <pkg>...` from the `tools/` root so each package resolves.

## Input Descriptions

| File | Description |
|------|-------------|
| `story.md` | Clean short story ("The 3:47 Email"). Ready for direct TTS. |
| `noisy_story.md` | Reddit post with injected noise (Edit:, awards, HTML). Needs cleanup. |
| `dialogue_story.md` | Multi-character story ("Let's Eat Humans") with distinct dialogue. |
| `chinese_text.md` | Short Chinese prose with embedded English. Tests language detection. |
| `multi_speaker.WAV` | Real two-person Chinese interview. Tests diarization. |
| `summarize_instructions.md` | English instruction file (legacy, for reference). |
| `chinese_summary_instructions.md` | Chinese instruction file with speaker identity (legacy, for reference). |
