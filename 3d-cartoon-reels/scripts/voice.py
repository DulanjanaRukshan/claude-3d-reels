"""Generate both character voices with Kokoro TTS (runs locally, no API key) and build the timing files.

Usage: python3 scripts/voice.py script.json
Writes: audio/vo.wav, build/lines.json, build/words.json, build/env.json
"""
import json, re, subprocess, sys, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

SR, FPS, GAP, LEAD, TAIL = 24000, 30, 0.14, 0.25, 1.6
cfg = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'script.json'))
VOICES = cfg['voices']
SPOKEN_LEN = cfg.get('spoken_len', {})
k = Kokoro('assets/kokoro.onnx', 'assets/voices.bin')

def pitch(a, f):
    if abs(f - 1) < 1e-3: return a
    sf.write('build/_in.wav', a, SR)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'build/_in.wav', '-af',
                    f'asetrate={int(SR * f)},aresample={SR},atempo={1 / f:.5f}', 'build/_out.wav'], check=True)
    return sf.read('build/_out.wav')[0]

def segments(a, thr_db=-38, min_sil=0.12):
    hop = int(SR * 0.01); n = len(a) // hop
    rms = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    voiced = 20 * np.log10(rms / (rms.max() + 1e-9)) > thr_db
    segs, i = [], 0
    while i < n:
        if voiced[i]:
            j = i
            while j < n and voiced[j]: j += 1
            segs.append([i, j]); i = j
        else: i += 1
    merged = []
    for s in segs:
        if merged and (s[0] - merged[-1][1]) < min_sil * 100: merged[-1][1] = s[1]
        else: merged.append(s)
    return [(s * hop, e * hop) for s, e in merged]

def tighten(a):
    """Trim edges and shrink pauses inside a line to 0.2 s. Returns audio + voiced phrase spans (s)."""
    pad = int(0.03 * SR); out, spans, t = [], [], 0
    for idx, (s, e) in enumerate(segments(a)):
        chunk = a[max(0, s - pad):min(len(a), e + pad)]
        if idx: out.append(np.zeros(int(0.2 * SR))); t += 0.2
        spans.append((t, t + len(chunk) / SR)); out.append(chunk); t += len(chunk) / SR
    return np.concatenate(out), spans

def ww(w):
    return SPOKEN_LEN.get(w, max(2, len(re.sub(r'[^A-Za-z]', '', w))) + 1)

def word_times(show, spans, t0, dur):
    """Approximate word timings: split the caption into phrases at punctuation, match phrases to the
    voiced spans found in the audio, then share each span between its words by spoken length."""
    words = show.split(); phrases, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r'[.,!?]$', w) and not re.match(r'^\d+\.\d+$', w): phrases.append(cur); cur = []
    if cur: phrases.append(cur)
    groups = list(zip(phrases, spans)) if len(phrases) == len(spans) else [(words, (0, dur))]
    out = []
    for ph, (a, b) in groups:
        tot = sum(ww(w) for w in ph); t = a
        for w in ph:
            d = (b - a) * ww(w) / tot
            out.append({'w': w, 's': round(t0 + t, 3), 'e': round(t0 + t + d, 3)}); t += d
    return out

audio, lines, words, t = [np.zeros(int(LEAD * SR))], [], [], LEAD
for i, L in enumerate(cfg['lines']):
    v = VOICES[L['spk']]
    a, _ = k.create(L.get('say', L['text']), voice=v['voice'], speed=v.get('speed', 1.0), lang='en-us')
    a = pitch(a.astype(np.float64), v.get('pitch', 1.0))
    a, spans = tighten(a)
    a = np.clip(a * (0.12 / np.sqrt(np.mean(a[np.abs(a) > 0.01] ** 2))), -0.98, 0.98)  # loudness-match voices
    dur = len(a) / SR
    lw = word_times(L['text'], spans, t, dur)
    for w in lw: w['line'] = i; w['kw'] = w['w'] in L.get('kw', [])
    words += lw
    lines.append({'i': i, 'spk': L['spk'], 'text': L['text'], 's': round(t, 3), 'e': round(t + dur, 3)})
    audio += [a, np.zeros(int(GAP * SR))]; t += dur + GAP
audio.append(np.zeros(int(TAIL * SR)))
vo = np.concatenate(audio); sf.write('audio/vo.wav', vo, SR); total = len(vo) / SR

hop = SR // FPS
env = np.array([float(np.sqrt(np.mean(vo[f * hop:(f + 1) * hop] ** 2))) if len(vo[f * hop:(f + 1) * hop]) else 0.0
                for f in range(int(total * FPS) + 1)])
env = np.clip(env / np.percentile(env[env > 0.005], 95), 0, 1)
json.dump(lines, open('build/lines.json', 'w'), indent=1)
json.dump(words, open('build/words.json', 'w'))
json.dump([round(x, 3) for x in env], open('build/env.json', 'w'))
print(f'total {total:.2f}s, {len(lines)} lines, {len(words)} words')
for l in lines: print(f"{l['s']:6.2f}-{l['e']:6.2f} {l['spk']}: {l['text']}")
