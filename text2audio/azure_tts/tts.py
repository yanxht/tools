"""Azure Neural TTS synthesis: chunking, synthesis, stitching (self-contained)."""
import os
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment
from xml.sax.saxutils import escape

MAX_CHUNK_SIZE = 3000


def _chunk_text(text: str, max_size: int = MAX_CHUNK_SIZE) -> list:
    """Split text into ≤max_size-char chunks at paragraph boundaries.

    Paragraphs longer than max_size are hard-split. This mirrors the proven
    chunking used in production and keeps each Azure request within limits.
    """
    paragraphs = text.split("\n")
    chunks = []
    current = ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(p) > max_size:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(p), max_size):
                chunks.append(p[i:i + max_size])
            continue
        if len(current) + len(p) < max_size:
            current += p + "\n"
        else:
            chunks.append(current.strip())
            current = p + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _synthesize_chunk(chunk_text, voice_name, rate, speech_key, region, out_path):
    """Synthesize one chunk to an MP3 file. Returns True on success."""
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=region)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    safe_text = escape(chunk_text)
    ssml = (
        "<speak version='1.0' xml:lang='en-US' "
        "xmlns='http://www.w3.org/2001/10/synthesis' "
        "xmlns:mstts='http://www.w3.org/2001/mstts'>"
        f"<voice name='{voice_name}'><prosody rate='{rate}'>{safe_text}</prosody></voice>"
        "</speak>"
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )
    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return True
    print(f"  ✗ TTS failed: {result.reason}")
    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        print(f"    Reason: {details.reason} | {details.error_details}")
    return False


def synthesize(text, output_path, speech_key, region, voice_name=None,
               language=None, gender="Female", rate="0.92"):
    """Synthesize `text` to `output_path` (MP3). Returns True on success."""
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    if not voice_name:
        from . import voices
        locale = language or voices.detect_locale(text)
        voice_name = voices.resolve_voice(locale, gender)
    print(f"  Voice: {voice_name}")

    chunks = _chunk_text(text)
    print(f"  Chunks: {len(chunks)}")

    temp_files = []
    combined = AudioSegment.empty()
    try:
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            temp_file = f"{abs_output}_temp_{i}.mp3"
            temp_files.append(temp_file)
            print(f"  Synthesizing chunk {i + 1}/{len(chunks)}...", end=" ", flush=True)
            if _synthesize_chunk(chunk, voice_name, rate, speech_key, region, temp_file):
                combined += AudioSegment.from_file(temp_file, format="mp3")
                print("✓")
            else:
                print(f"\n  ✗ Failed at chunk {i + 1}.")
                return False

        combined.export(abs_output, format="mp3")
        print(f"  Output: {abs_output}")
        return True
    except Exception as e:
        print(f"🔥 CRASH: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
