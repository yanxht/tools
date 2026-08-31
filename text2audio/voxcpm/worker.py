"""VoxCPM2 synthesis worker.

This script runs INSIDE the heavy venv (VOXCPM_VENV), which has voxcpm + torch
installed. It is invoked as:

    <VOXCPM_VENV> worker.py <text_path> <ref_path> <out_path> <result_path>

It clones the reference voice, synthesizes the text in short chunks, stitches
them, and writes a 16kHz mono MP3. The result JSON goes to <result_path> (not
stdout) because VoxCPM2's tqdm progress bars pollute stdout.
"""

import json
import os
import sys


def main():
    text_path, ref_path, out_path, result_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    def emit(ok, **kw):
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump({"ok": ok, **kw}, fh)

    try:
        with open(text_path, encoding="utf-8") as fh:
            text = fh.read().strip()
        if not text:
            emit(False, error="empty text")
            return

        from voxcpm import VoxCPM

        # Fastest accelerator: CUDA -> MPS -> CPU.
        import torch
        if torch.cuda.is_available():
            device, optimize = "cuda", True
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device, optimize = "mps", False
        else:
            device, optimize = "cpu", False

        try:
            model = VoxCPM.from_pretrained(
                "openbmb/VoxCPM2", load_denoiser=False, device=device, optimize=optimize
            )
        except Exception:
            model = VoxCPM.from_pretrained(
                "openbmb/VoxCPM2", load_denoiser=False, device="cpu", optimize=False
            )
        print(f"[voxcpm] device: {model.tts_model.device}", file=sys.stderr)
        sr = model.tts_model.sample_rate

        import numpy as np
        from pydub import AudioSegment

        # Chunk to keep each VoxCPM2 utterance short and stable.
        MAX = 120
        sentences = [s.strip() for s in text.split("\n") if s.strip()]
        chunks = []
        cur = ""
        for s in sentences:
            if len(cur) + len(s) + 1 <= MAX:
                cur = (cur + " " + s).strip()
            else:
                if cur:
                    chunks.append(cur)
                while len(s) > MAX:
                    chunks.append(s[:MAX])
                    s = s[MAX:]
                cur = s
        if cur:
            chunks.append(cur)

        combined = None
        for chunk in chunks:
            wav = model.generate(
                text="(steady narrator pace, clear articulation, neutral tone)" + chunk,
                reference_wav_path=ref_path,
                cfg_value=1.8,
                inference_timesteps=20,
            )
            seg = AudioSegment(
                (np.asarray(wav) * 32767).astype(np.int16).tobytes(),
                frame_rate=sr, sample_width=2, channels=1,
            )
            combined = seg if combined is None else combined + seg

        combined = combined.set_frame_rate(16000).set_channels(1)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        combined.export(
            out_path, format="mp3",
            parameters=["-ar", "16000", "-ab", "32k", "-ac", "1"],
        )
        emit(True, duration=round(len(combined) / 1000, 1))
    except Exception as e:
        emit(False, error=str(e))


if __name__ == "__main__":
    main()
