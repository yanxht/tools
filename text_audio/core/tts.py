import os
import re
import sys
import langid
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment
from xml.sax.saxutils import escape
from . import chunker

VOICE_MAP = {
    "en-US": {"Female": "en-US-AvaMultilingualNeural", "Male": "en-US-AndrewMultilingualNeural"},
    "en-GB": {"Female": "en-GB-SoniaNeural", "Male": "en-GB-RyanNeural"},
    "zh-CN": {"Female": "zh-CN-XiaoxiaoMultilingualNeural", "Male": "zh-CN-YunyiMultilingualNeural"},
    "zh-TW": {"Female": "zh-TW-HsiaoChenNeural", "Male": "zh-TW-YunJheNeural"},
    "ja-JP": {"Female": "ja-JP-NanamiNeural", "Male": "ja-JP-KeitaNeural"},
    "ko-KR": {"Female": "ko-KR-SunHiNeural", "Male": "ko-KR-InJoonNeural"},
    "es-ES": {"Female": "es-ES-ElviraNeural", "Male": "es-ES-AlvaroNeural"},
    "fr-FR": {"Female": "fr-FR-DeniseNeural", "Male": "fr-FR-HenriNeural"},
    "de-DE": {"Female": "de-DE-KatjaNeural", "Male": "de-DE-ConradNeural"},
}

# Map langid language codes to Azure locale codes
LANGID_TO_LOCALE = {
    "en": "en-US", "zh": "zh-CN", "ja": "ja-JP", "ko": "ko-KR",
    "es": "es-ES", "fr": "fr-FR", "de": "de-DE",
}


def detect_locale(text: str) -> str:
    lang, _ = langid.classify(text)
    return LANGID_TO_LOCALE.get(lang, "en-US")


def resolve_voice(locale: str, gender: str = "Female") -> str:
    """Resolve voice name from locale and gender, with fallback."""
    # Exact match
    if locale in VOICE_MAP:
        return VOICE_MAP[locale].get(gender, VOICE_MAP[locale]["Female"])
    # Language prefix match (e.g., zh-TW -> zh-CN)
    prefix = locale.split("-")[0]
    for key in VOICE_MAP:
        if key.startswith(prefix + "-"):
            return VOICE_MAP[key].get(gender, VOICE_MAP[key]["Female"])
    # Fallback to en-US
    return VOICE_MAP["en-US"].get(gender, VOICE_MAP["en-US"]["Female"])


def print_voice_table():
    print(f"\n{'Language':<22} {'Locale':<10} {'Female Voice':<40} {'Male Voice'}")
    print("-" * 110)
    names = {
        "en-US": "English (US)", "en-GB": "English (UK)", "zh-CN": "Chinese (Mandarin)",
        "zh-TW": "Chinese (Taiwanese)", "ja-JP": "Japanese", "ko-KR": "Korean",
        "es-ES": "Spanish", "fr-FR": "French", "de-DE": "German",
    }
    for locale, voices in VOICE_MAP.items():
        name = names.get(locale, locale)
        print(f"{name:<22} {locale:<10} {voices['Female']:<40} {voices['Male']}")
    print()


def _synthesize_chunk(text: str, voice_name: str, rate: str, speech_key: str,
                       region: str, output_path: str) -> bool:
    """Synthesize a single chunk of text to an MP3 file."""
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=region)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    safe_text = escape(text)
    ssml = f"""<speak version='1.0' xml:lang='en-US'
        xmlns='http://www.w3.org/2001/10/synthesis'
        xmlns:mstts='http://www.w3.org/2001/mstts'>
    <voice name='{voice_name}'>
        <prosody rate='{rate}'>
            {safe_text}
        </prosody>
    </voice>
</speak>"""

    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return True
    else:
        print(f"  ✗ TTS failed: {result.reason}")
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            print(f"    Reason: {details.reason} | {details.error_details}")
        return False


def _synthesize_chunk_multi_voice(text: str, speaker_voices: dict, rate: str,
                                    speech_key: str, region: str, output_path: str) -> bool:
    """
    Synthesize a chunk that may contain multiple speaker labels.
    speaker_voices: {"Speaker 1": "en-US-AvaMultilingualNeural", "Speaker 2": "en-US-AndrewMultilingualNeural"}
    """
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=region)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    # Parse speaker labels and build multi-voice SSML
    # Pattern: [Speaker N]: text
    pattern = re.compile(r'\[(Speaker \d+)\]:\s*')
    parts = pattern.split(text)

    # parts alternates: [text_before, speaker_label, text, speaker_label, text, ...]
    ssml_body = ""
    current_voice = list(speaker_voices.values())[0]  # default to first speaker

    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if part in speaker_voices:
            current_voice = speaker_voices[part]
            i += 1
            continue
        if part:
            safe_text = escape(part)
            ssml_body += f"""    <voice name='{current_voice}'>
        <prosody rate='{rate}'>
            {safe_text}
        </prosody>
    </voice>\n"""
        i += 1

    if not ssml_body:
        return True  # empty chunk

    ssml = f"""<speak version='1.0' xml:lang='en-US'
        xmlns='http://www.w3.org/2001/10/synthesis'
        xmlns:mstts='http://www.w3.org/2001/mstts'>
{ssml_body}</speak>"""

    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return True
    else:
        print(f"  ✗ TTS failed: {result.reason}")
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            print(f"    Reason: {details.reason} | {details.error_details}")
        return False


def synthesize(text: str, output_path: str, speech_key: str, region: str,
               voice_name: str = None, language: str = None, gender: str = "Female",
               rate: str = "0.92", multi_voice: bool = False,
               speaker_voices: dict = None) -> bool:
    """
    Main TTS entry point. Chunks text, synthesizes each chunk (with checkpoint),
    and stitches into final MP3.

    For multi_voice mode, speaker_voices must be provided:
        {"Speaker 1": "voice-name", "Speaker 2": "voice-name"}
    """
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    # Resolve voice
    if not multi_voice:
        if not voice_name:
            locale = language or detect_locale(text)
            voice_name = resolve_voice(locale, gender)
        print(f"  Voice: {voice_name}")

    # Chunk the text
    chunks = chunker.chunk_text(text)
    total = len(chunks)
    print(f"  Chunks: {total}")

    # Setup checkpoints
    ckpt_dir = chunker.get_checkpoint_dir(abs_output)
    completed = chunker.get_completed_chunks(ckpt_dir)
    if completed:
        print(f"  Resuming: {len(completed)} chunks already done")

    # Synthesize each chunk
    for i, chunk_text_piece in enumerate(chunks):
        if i in completed:
            continue

        chunk_path = chunker.get_chunk_path(ckpt_dir, i)
        print(f"  Synthesizing chunk {i + 1}/{total}...", end=" ", flush=True)

        if multi_voice and speaker_voices:
            ok = _synthesize_chunk_multi_voice(
                chunk_text_piece, speaker_voices, rate, speech_key, region, chunk_path
            )
        else:
            ok = _synthesize_chunk(chunk_text_piece, voice_name, rate, speech_key, region, chunk_path)

        if ok:
            print("✓")
        else:
            print(f"\n  ✗ Failed at chunk {i + 1}. Checkpoints saved in {ckpt_dir}")
            print("  Re-run the same command to resume from this point.")
            return False

    # Stitch all chunks
    print("  Stitching audio...", end=" ", flush=True)
    combined = AudioSegment.empty()
    for i in range(total):
        chunk_path = chunker.get_chunk_path(ckpt_dir, i)
        segment = AudioSegment.from_file(chunk_path, format="mp3")
        combined += segment

    combined.export(abs_output, format="mp3")
    print("✓")

    # Cleanup checkpoints
    chunker.cleanup_checkpoints(ckpt_dir)
    print(f"  Output: {abs_output}")
    return True
