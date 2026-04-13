# Tests

All test inputs and outputs are committed to the repo so users can inspect real results and experiment with the tool.

## Test Matrix

### text2audio (Text → Audio)

| # | Scenario | Input | Flags | Output | Notes |
|---|----------|-------|-------|--------|-------|
| 1 | Clean English, auto-detect | [clean_story.md](inputs/clean_story.md) | — | [test1_clean_en.mp3](outputs/test1_clean_en.mp3) | Auto-detected `en-US`, picked `Ava` (Female), 2 chunks |
| 2 | Noisy text + AI cleanup | [noisy_story.md](inputs/noisy_story.md) | `--ai --prompt prompts/default_clean.md` | [test2_noisy_ai.mp3](outputs/test2_noisy_ai.mp3) | AI stripped Reddit noise (6841→6455 chars), 3 chunks |
| 3 | Chinese, auto-detect language | [chinese_text.md](inputs/chinese_text.md) | — | [test3_chinese_auto.mp3](outputs/test3_chinese_auto.mp3) | Auto-detected `zh-CN`, picked `Xiaoxiao` (Female). Mixed Chinese/English text ("The Art of War") handled natively |
| 4 | Chinese, explicit male voice | [chinese_text.md](inputs/chinese_text.md) | `--voice zh-CN-YunyiMultilingualNeural` | [test4_chinese_male.mp3](outputs/test4_chinese_male.mp3) | Same text, male `Yunyi` voice |
| 5 | Multi-voice dialogue | [dialogue_story.md](inputs/dialogue_story.md) | `--multi-voice` | [test5_multivoice.mp3](outputs/test5_multivoice.mp3) | LLM inferred 6 speakers with correct genders, 4 chunks |
| 6 | Fast speech rate | [clean_story.md](inputs/clean_story.md) | `--rate 1.2` | [test6_fast_rate.mp3](outputs/test6_fast_rate.mp3) | 1.2× speed vs. default 0.92 |

### audio2text (Audio → Text)

| # | Scenario | Input | Flags | Output | Notes |
|---|----------|-------|-------|--------|-------|
| 7 | English single-speaker | [test1_clean_en.mp3](outputs/test1_clean_en.mp3)* | — | [test7_transcript.md](outputs/test7_transcript.md) | 333s audio, 18 segments, 1 speaker detected |
| 8 | English + AI summary | [test1_clean_en.mp3](outputs/test1_clean_en.mp3)* | `--ai --prompt` [summarize_instructions.md](inputs/summarize_instructions.md) | [test8_transcript_ai.md](outputs/test8_transcript_ai.md) + [test8_transcript_ai_ai.md](outputs/test8_transcript_ai_ai.md) | Raw transcript + AI-generated summary with key takeaways |
| 9 | Chinese single-speaker | [test3_chinese_auto.mp3](outputs/test3_chinese_auto.mp3)* | `--language zh-CN` | [test9_chinese_transcript.md](outputs/test9_chinese_transcript.md) | 73s, recognized Chinese + embedded English |
| 10 | Chinese multi-speaker | [multi_speaker.WAV](inputs/multi_speaker.WAV) | `--language zh-CN` | [test10_multi_speaker.md](outputs/test10_multi_speaker.md) | 105s, **2 speakers detected** via diarization |
| 11 | Multi-speaker + English AI summary | [multi_speaker.WAV](inputs/multi_speaker.WAV) | `--language zh-CN --ai --prompt` [summarize_instructions.md](inputs/summarize_instructions.md) | [test11_multi_speaker_ai.md](outputs/test11_multi_speaker_ai.md) + [test11_multi_speaker_ai_ai.md](outputs/test11_multi_speaker_ai_ai.md) | Demonstrates that instruction language controls output language |
| 12 | Multi-speaker + Chinese AI with speaker identity | [multi_speaker.WAV](inputs/multi_speaker.WAV) | `--language zh-CN --ai --prompt` [chinese_summary_instructions.md](inputs/chinese_summary_instructions.md) | [test12_chinese_ai.md](outputs/test12_chinese_ai.md) + [test12_chinese_ai_ai.md](outputs/test12_chinese_ai_ai.md) | Chinese instructions with known speaker names → AI correctly mapped Speaker 1 = 郑诗亮 (host), Speaker 2 = 王强 (guest) |

*These inputs are outputs from earlier text2audio tests, demonstrating the round-trip capability.

## Reproducing Tests

```bash
cd tools
source text_audio/.venv/bin/activate

# Test 1
python -m text_audio text2audio -i text_audio/tests/inputs/clean_story.md -o text_audio/tests/outputs/test1_clean_en.mp3

# Test 2
python -m text_audio text2audio -i text_audio/tests/inputs/noisy_story.md -o text_audio/tests/outputs/test2_noisy_ai.mp3 --ai --prompt text_audio/prompts/default_clean.md

# Test 3
python -m text_audio text2audio -i text_audio/tests/inputs/chinese_text.md -o text_audio/tests/outputs/test3_chinese_auto.mp3

# Test 4
python -m text_audio text2audio -i text_audio/tests/inputs/chinese_text.md -o text_audio/tests/outputs/test4_chinese_male.mp3 --voice zh-CN-YunyiMultilingualNeural

# Test 5
python -m text_audio text2audio -i text_audio/tests/inputs/dialogue_story.md -o text_audio/tests/outputs/test5_multivoice.mp3 --multi-voice

# Test 6
python -m text_audio text2audio -i text_audio/tests/inputs/clean_story.md -o text_audio/tests/outputs/test6_fast_rate.mp3 --rate 1.2

# Test 7
python -m text_audio audio2text -i text_audio/tests/outputs/test1_clean_en.mp3 -o text_audio/tests/outputs/test7_transcript.md

# Test 8
python -m text_audio audio2text -i text_audio/tests/outputs/test1_clean_en.mp3 -o text_audio/tests/outputs/test8_transcript_ai.md --ai --prompt text_audio/tests/inputs/summarize_instructions.md

# Test 9
python -m text_audio audio2text -i text_audio/tests/outputs/test3_chinese_auto.mp3 -o text_audio/tests/outputs/test9_chinese_transcript.md --language zh-CN

# Test 10
python -m text_audio audio2text -i text_audio/tests/inputs/multi_speaker.WAV -o text_audio/tests/outputs/test10_multi_speaker.md --language zh-CN

# Test 11
python -m text_audio audio2text -i text_audio/tests/inputs/multi_speaker.WAV -o text_audio/tests/outputs/test11_multi_speaker_ai.md --language zh-CN --ai --prompt text_audio/tests/inputs/summarize_instructions.md

# Test 12
python -m text_audio audio2text -i text_audio/tests/inputs/multi_speaker.WAV -o text_audio/tests/outputs/test12_chinese_ai.md --language zh-CN --ai --prompt text_audio/tests/inputs/chinese_summary_instructions.md
```

## Test Input Descriptions

| File | Description |
|------|-------------|
| `clean_story.md` | Clean short story from r/shortstories ("The 3:47 Email"). Ready for direct TTS. |
| `noisy_story.md` | Same source with injected Reddit noise: "Edit:", "TL;DR", HTML tags, social media handles. Needs AI cleanup. |
| `dialogue_story.md` | Multi-character story ("Let's Eat Humans") with distinct dialogue. Good for multi-voice testing. |
| `chinese_text.md` | Short Chinese prose with embedded English ("The Art of War"). Tests language detection and multilingual voice. |
| `multi_speaker.WAV` | Real two-person Chinese interview (郑诗亮 interviewing 王强 about books and reading). Tests diarization. |
| `summarize_instructions.md` | English instruction file: summarize, extract takeaways and quotes. |
| `chinese_summary_instructions.md` | Chinese instruction file with speaker identity context. Demonstrates prompt-driven output language and speaker mapping. |
