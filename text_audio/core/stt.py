import os
import threading
import time
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment


def transcribe(input_path: str, output_path: str, speech_key: str, region: str,
               language: str = "en-US") -> str:
    """
    Transcribe audio file using Azure Conversation Transcription with speaker diarization.
    Returns the raw transcript as a markdown-formatted string.

    Flow: audio file → pydub decode to PCM → push stream → ConversationTranscriber → collect events
    """
    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    print(f"  Loading audio: {abs_input}")

    # Decode to PCM via pydub (handles mp3, wav, etc.)
    audio = AudioSegment.from_file(abs_input)
    # Convert to format expected by Azure: 16kHz, mono, 16-bit PCM
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    pcm_data = audio.raw_data
    audio_duration_s = len(audio) / 1000.0

    print(f"  Audio duration: {audio_duration_s:.1f}s")
    print(f"  Language: {language}")

    # Setup push stream
    stream_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=16000, bits_per_sample=16, channels=1
    )
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=region)
    speech_config.speech_recognition_language = language

    transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=speech_config, audio_config=audio_config
    )

    # Collect results
    transcript_segments = []
    done_event = threading.Event()
    error_msg = []
    last_event_time = [time.time()]

    def on_transcribed(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            speaker = evt.result.speaker_id or "Unknown"
            text = evt.result.text.strip()
            if text:
                transcript_segments.append((speaker, text))
                last_event_time[0] = time.time()
                print(f"    [{speaker}]: {text[:60]}{'...' if len(text) > 60 else ''}")

    def on_canceled(evt):
        if evt.reason == speechsdk.CancellationReason.Error:
            error_msg.append(f"STT Error: {evt.error_details}")
        done_event.set()

    def on_session_stopped(evt):
        done_event.set()

    transcriber.transcribed.connect(on_transcribed)
    transcriber.canceled.connect(on_canceled)
    transcriber.session_stopped.connect(on_session_stopped)

    # Start transcription
    transcriber.start_transcribing_async().get()

    # Push audio frames in a background thread so we can monitor progress
    def push_audio():
        FRAME_SIZE = 3200  # 100ms of 16kHz 16-bit mono
        offset = 0
        while offset < len(pcm_data):
            end = min(offset + FRAME_SIZE, len(pcm_data))
            push_stream.write(pcm_data[offset:end])
            offset = end
        push_stream.close()

    push_thread = threading.Thread(target=push_audio, daemon=True)
    push_thread.start()

    print("  Transcribing...", flush=True)

    # Wait for: session_stopped/canceled event, OR inactivity timeout after all audio pushed.
    # The SDK processes audio in ~real-time, so events arrive over the full audio duration
    # even after all frames are pushed at once.
    push_thread.join()
    last_event_time[0] = time.time()  # reset after all audio pushed

    # Wait: at least audio_duration (real-time processing), then check for inactivity
    INACTIVITY_TIMEOUT = 30  # seconds of no new events after audio should be fully processed
    min_wait_until = time.time() + audio_duration_s + 5  # at least audio duration + 5s buffer

    while not done_event.is_set():
        now = time.time()
        # Don't timeout before the minimum wait period
        if now < min_wait_until:
            done_event.wait(timeout=1.0)
            continue
        # After minimum wait, check for inactivity
        if now - last_event_time[0] > INACTIVITY_TIMEOUT:
            break
        done_event.wait(timeout=1.0)

    # Proactively stop the transcriber
    transcriber.stop_transcribing_async().get()

    if error_msg:
        print(f"  ✗ {error_msg[0]}")
        return None

    if not transcript_segments:
        print("  ✗ No speech detected in audio.")
        return None

    # Build markdown output
    # Normalize speaker IDs to sequential labels
    speaker_map = {}
    speaker_count = 0
    lines = []

    for speaker, text in transcript_segments:
        if speaker not in speaker_map:
            speaker_count += 1
            speaker_map[speaker] = f"Speaker {speaker_count}"
        label = speaker_map[speaker]
        lines.append(f"[{label}]: {text}")

    # Header
    header = f"# Transcript\n\n"
    header += f"- **Source:** {os.path.basename(abs_input)}\n"
    header += f"- **Language:** {language}\n"
    header += f"- **Speakers detected:** {speaker_count}\n"
    header += f"- **Duration:** {len(audio) / 1000:.1f}s\n\n"
    header += "---\n\n"

    transcript_text = header + "\n\n".join(lines) + "\n"

    # Write output
    with open(abs_output, "w", encoding="utf-8") as f:
        f.write(transcript_text)

    print(f"  ✓ Transcript: {abs_output}")
    print(f"    {len(transcript_segments)} segments, {speaker_count} speaker(s)")

    return transcript_text
