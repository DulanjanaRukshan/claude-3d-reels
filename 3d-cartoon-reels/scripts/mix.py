"""Usage: python3 scripts/mix.py script.json
Synthesize SFX + a calm music loop (all generated here, no downloads), duck music under voice, mix to -14 LUFS -> build/mix.wav"""
import json, subprocess, sys, numpy as np, soundfile as sf

SR = 48000
CFG = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'script.json')).get('sfx', {})
L = json.load(open('build/lines.json')); WD = json.load(open('build/words.json'))
DUR = int(np.ceil((L[-1]['e'] + 1.6) * 30)) / 30
N = int(DUR * SR) + SR
rng = np.random.default_rng(3)
t_ = lambda d: np.arange(int(d * SR)) / SR

def env_ad(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(t / max(a, 1e-4), 1) * np.exp(-t / d)

def lp(x, k):  # one-pole lowpass, k in 0..1
    y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)): acc += k * (x[i] - acc); y[i] = acc
    return y

def whoosh():
    d = .45; t = t_(d); n = rng.standard_normal(len(t))
    cut = np.linspace(.02, .35, len(t)) ** 1.5 * (1 - t / d) + .01
    y = np.zeros_like(n); acc = 0.0
    for i in range(len(n)): acc += cut[i] * (n[i] - acc); y[i] = acc
    e = np.sin(np.pi * t / d) ** 2
    return y * e * 2.2

def pop():
    t = t_(.12); f = 900 * np.exp(-t * 25) + 420
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(len(t), .002, .03) * .7

def click():
    t = t_(.03); return rng.standard_normal(len(t)) * env_ad(len(t), .0005, .006) * .35

def impact():
    t = t_(.5); f = 110 * np.exp(-t * 6) + 45
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(len(t), .002, .18)
    nz = lp(rng.standard_normal(len(t)), .15) * env_ad(len(t), .001, .05)
    return (body * .9 + nz * 1.2)

def chime():
    t = t_(2.2); y = np.zeros_like(t)
    for f, a in [(1046.5, 1), (1318.5, .6), (1568, .5), (2093, .25)]:
        y += a * np.sin(2 * np.pi * f * t) * np.exp(-t * (1.6 + f / 1500))
    return y * .25 * np.minimum(t / .005, 1)

def tick():
    t = t_(.05); return np.sin(2 * np.pi * 1800 * t) * env_ad(len(t), .001, .012) * .25

sfx = np.zeros(N)
def put(x, at, g=1.0):
    i = int(at * SR); j = min(N, i + len(x)); sfx[i:j] += x[:j - i] * g

# whoosh on every camera cut
for l in L[1:]: put(whoosh(), l['s'] - .2, .5)
def wt(li, w): return next(x for x in WD if x['line'] == li and x['w'].strip('.,!?') == w.strip('.,!?'))
LAST = len(L) - 1
# pop when a card appears / when the top chip changes
for li in CFG.get('card_lines', []): put(pop(), L[li]['s'] + .05, .8)
for li in CFG.get('chip_lines', []): put(pop(), L[li]['s'] - .02, .5)
# impacts: [line, word, offset_s, gain]
for li, w, off, gn in CFG.get('impacts', []): put(impact(), wt(li, w)['s'] + off, gn)
# typing clicks: [line, word, delay_after_word_end, duration]
for li, w, dl, du in CFG.get('typing', []):
    st = wt(li, w)['e'] + dl
    for k in range(int(du / .055)): put(click(), st + k * .055 + rng.uniform(0, .015), .8)
# counter ticks: [line, from_word, to_word, extra_from, extra_to]
for li, a, b, ea, eb in CFG.get('counters', []):
    t0 = wt(li, a)['s'] + ea; t1 = max(wt(li, b)['e'], wt(li, a)['e'] + eb)
    for x in np.arange(t0, t1, .11): put(tick(), x, .18)
# call to action on the last line
if CFG.get('cta_impact_word'): put(impact(), wt(LAST, CFG['cta_impact_word'])['s'] - .05, 1.0)
if CFG.get('cta_click_word'): w = wt(LAST, CFG['cta_click_word']); put(click() * 3, w['s'], 1.0); put(chime() * .6, w['s'] + .05, .8)
put(chime(), wt(LAST, CFG.get('cta_chime_word') or WD[-1]['w'])['s'], 1.0)

# ---- calm music loop: Fmaj7 - Am7 - Dm9 - Bbmaj7 pad + soft pluck arp + light kick ----
bpm = 92; beat = 60 / bpm; bar = beat * 4
chords = [[53, 57, 60, 64], [57, 60, 64, 67], [50, 57, 60, 64, 65], [46, 53, 57, 62]]
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
mus = np.zeros(N)
nb = int(DUR / bar) + 2
for b in range(nb):
    ch = chords[b % 4]; i0 = int(b * bar * SR); n = int(bar * SR * 1.05)
    t = np.arange(n) / SR
    pad = sum(np.sin(2 * np.pi * hz(m) * t) + .3 * np.sin(2 * np.pi * hz(m) * 2.003 * t) for m in ch)
    pad *= np.minimum(t / .6, 1) * np.minimum((bar * 1.05 - t) / .4, 1) * .045
    j = min(N, i0 + n); mus[i0:j] += pad[:max(0, j - i0)] if i0 < N else 0
    for s in range(8):  # arp eighths
        m = ch[[0, 2, 1, 3, 2, 1, 3, 2][s] % len(ch)] + 12
        tt = t_(.5); x = np.sin(2 * np.pi * hz(m) * tt) * env_ad(len(tt), .004, .16) * .05
        k = i0 + int(s * beat / 2 * SR); j = min(N, k + len(x)); mus[k:j] += x[:max(0, j - k)] if k < N else 0
    for s in range(4):  # soft kick + hat
        tt = t_(.3); f = 120 * np.exp(-tt * 30) + 48
        kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(len(tt), .001, .09) * .22
        k = i0 + int(s * beat * SR); j = min(N, k + len(kick)); mus[k:j] += kick[:max(0, j - k)] if k < N else 0
        hh = rng.standard_normal(int(.04 * SR)); hh = (hh - lp(hh, .3)) * env_ad(len(hh), .0005, .01) * .05
        k2 = k + int(beat / 2 * SR); j = min(N, k2 + len(hh)); mus[k2:j] += hh[:max(0, j - k2)] if k2 < N else 0
mus = lp(mus, .5)
fade = np.ones(N); fe = int(DUR * SR); fo = int(1.2 * SR); fade[fe - fo:fe] = np.linspace(1, 0, fo); fade[fe:] = 0
mus *= fade
fi = int(.4 * SR); mus[:fi] *= np.linspace(0, 1, fi)

sf.write('build/sfx.wav', np.clip(sfx[:int(DUR * SR)] * .5, -1, 1), SR)
sf.write('build/music.wav', np.clip(mus[:int(DUR * SR)], -1, 1), SR)
# duck music under voice with sidechain, then mix + loudnorm
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'audio/vo.wav', '-i', 'build/music.wav', '-i', 'build/sfx.wav', '-filter_complex',
  '[0:a]aresample=48000,asplit=2[v][sc];'
  '[1:a][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[m];'
  '[v]volume=1.0[vv];[m]volume=0.8[mm];[2:a]volume=0.9[ss];'
  '[vv][mm][ss]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-13.2:TP=-1.5:LRA=11,aresample=48000[o]',
  '-map', '[o]', '-t', f'{DUR}', '-ac', '2', 'build/mix.wav'], check=True)
print('mix ok', DUR)
