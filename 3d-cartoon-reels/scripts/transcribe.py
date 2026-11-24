"""Transcribe a wav/mp4 in ~25 s chunks with sherpa-onnx whisper base.en. Usage: python3 transcribe.py file"""
import sys, subprocess, numpy as np, sherpa_onnx
d = 'assets/sherpa-onnx-whisper-base.en/'
rec = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=d + 'base.en-encoder.int8.onnx', decoder=d + 'base.en-decoder.int8.onnx',
                                                tokens=d + 'base.en-tokens.txt', num_threads=2)
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', sys.argv[1], '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                     capture_output=True, check=True).stdout
a = np.frombuffer(raw, dtype=np.float32)
# split at quiet points near every 20 s
out, pos, sr = [], 0, 16000
while pos < len(a):
    end = min(len(a), pos + 14 * sr)
    if end < len(a):
        win = a[end:end + 5 * sr]
        e = np.array([np.abs(win[i:i + 1600]).mean() for i in range(0, len(win) - 1600, 800)])
        end += int(np.argmin(e)) * 800 + 800
    s = rec.create_stream(); s.accept_waveform(sr, a[pos:end]); rec.decode_stream(s)
    out.append(s.result.text.strip()); pos = end
print(' '.join(out))
