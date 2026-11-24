---
name: 3d-cartoon-reels
description: Make a vertical 3D cartoon YouTube Short or Reel (voxel creator + orange sidekick explaining a topic) built entirely with code - Three.js scene, local AI voices, synced captions, cards, SFX and music. Use when asked for a 3D cartoon reel, Short, or explainer video in this style.
---

# 3D Cartoon Reels

Builds a 1080x1920, 30 fps MP4 where a blocky (voxel) version of the creator and a little orange
block sidekick talk through a topic. It is not AI video: a Three.js page draws every frame from the
time `t`, headless Chrome screenshots each frame, and ffmpeg encodes them. Voices are generated
locally with Kokoro TTS. Sound effects and music are synthesized in Python, so no downloads or
API keys are needed after setup.

Example output: `examples/voyager-light-day/` (52 s, 17 lines, science news).

## Requirements
Node 18+, Python 3.10+, ffmpeg, Google Chrome (or set `CHROME_PATH`). Everything else is installed
by `scripts/setup.sh`. That script downloads the Kokoro voice model (~350 MB) and a small Whisper
model from GitHub releases.

## Workflow

Work in a fresh, empty project folder. Show the user progress at each checkpoint.

### 1. Gather details (ask once, with defaults)
- Topic. If they want something "trending", web-search current news and pick one story with
  strong numbers. Verify every fact against primary sources (NASA, journals, official sites).
- Character look (hair, beard, clothes, skin tone), sidekick (default: orange block, ^ ^ eyes).
- Length (default 40-55 s, keep under 60 s for Shorts) and the call to action (for example
  "Subscribe to my channel for more videos like this!").
- Voices: male or female "me"; the sidekick defaults to a pitched-up cute voice.

### 2. Set up
```bash
bash <skill>/scripts/setup.sh
```
This copies `render.js voice.py mix.py transcribe.py comp.html` into the project. Then prove
rendering works: `node render.js stills build/st 1`.

### 3. Script -> `script.json`
Copy `examples/voyager-light-day/script.json` and rewrite it. Rules:
- The first 3 seconds hook: name the surprise right away.
- Lines of 3-10 words. Each line belongs to one speaker: `me` or `sk`.
- The sidekick teaches in numbered steps ("Step one. ...", "Step two. ...", "Step three. ...").
- One deadpan joke beat in the middle helps retention.
- The last line is the call to action, said by `me`.
- `text` is the caption (digits are fine). `say` is what the voice reads: spell numbers out
  ("twenty-five point nine billion"). `kw` lists the caption words to show in yellow, exactly as
  they appear in `text`, punctuation included.
- `spoken_len` gives an approximate spoken letter count for digit tokens, so the word timings
  stay accurate.
- Also write `script.md` (# | speaker | line | on screen) for the user.
- CHECKPOINT: show the script and wait for approval.

Kokoro voices: male `am_michael` (default), `am_adam`, `am_fenrir`, `am_puck`, `bm_george`;
female `af_heart` (default sidekick, with `pitch: 1.13`), `af_bella`, `af_nicole`, `af_sky`,
`bf_emma`.

### 4. Voices
```bash
python3 voice.py script.json
python3 transcribe.py audio/vo.wav    # must match the script word for word
```
Writes `audio/vo.wav`, `build/lines.json`, `build/words.json`, `build/env.json`. If a word is
misheard, change `say` (add commas, spell it out) and rerun. Send the user an mp3 preview.

### 5. Scene -> edit the PER-VIDEO CONFIG in `comp.html`
The template is the finished Voyager reel. Keep the generic parts: renderer, lights, grid,
characters, camera maths, captions, confetti. Rewrite these for each video:
- **Character colours and boxes**: `SKIN, HAIR, TEE, JEANS`, the hair/beard boxes, and the
  sidekick colour `CLAY`. Remove the beard boxes for a clean-shaven look, and so on.
- **Topic props**: the Voyager probe and Earth are props. Replace them with voxel props for the
  new topic, or delete them.
- **`PLAN`**: one shot per line, using keys of `SHOT`. Use a close-up of whoever talks
  (`cuMe`, `cuSk`), a wide shot on "Step" lines, `tightMe` for a joke beat, `end` for the last
  line. It must have exactly as many entries as there are lines.
- **`SERIOUS_LINES`**: lines where the sidekick's eyes switch to `| |`.
- **`CHIPS`**: the top label per section. `step` fills the 3 progress dashes.
- **`CARDS`**: one animated panel per line that needs one. Use `W_(line, 'word')` to time
  animations to spoken words: counters, typed text (`typed()`), stamps (`withPop`), clocks,
  checklists. Cards live between y=270 and y=700. Don't cover faces.
- **`drawEnding()`**: the call-to-action graphic on the last line (the template has a red
  SUBSCRIBE button, a ringing bell and confetti).
- **`renderThumb()`**: the thumbnail title text.

Layout rules: chip at y≈110-230, cards y≈270-700, faces y≈750-1350, captions at y=1640.
In close-ups the whole head must fit with room around it.

### 6. Check stills (contact sheet)
```bash
node render.js stills build/st $(python3 -c "import json;print(' '.join(f\"{min(l['e']-.1,l['s']+1.3):.2f}\" for l in json.load(open('build/lines.json'))))")
ffmpeg -y -pattern_type glob -i 'build/st/*.jpg' -vf "scale=300:-1,tile=9x2:padding=6" build/sheet.jpg
```
Look at the sheet and fix every problem: cut-off faces, text over faces, overlapping cards,
empty panels (make their content appear within about 0.3 s of the line start), ugly framing.
Re-render the stills and look again.

### 7. Sound, render, verify
Edit the `sfx` block in `script.json` (card lines, chip lines, impacts, typing, counters, CTA
words), then:
```bash
python3 mix.py script.json                      # build/mix.wav, about -14 LUFS
node render.js video build/video.mp4 -          # about 0.3 s/frame on 2 CPUs; run in background
ffmpeg -y -i build/mix.wav -af "volume=1.1dB,alimiter=limit=0.84:level=false" build/mix2.wav
ffmpeg -y -i build/video.mp4 -i build/mix2.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart final.mp4
ffmpeg -i final.mp4 -af ebur128 -f null - 2>&1 | grep " I:"     # target about -14 LUFS
python3 transcribe.py final.mp4                                    # must match the script
```
If the SFX mask a word in the transcript, lower that cue and remix.
Thumbnail: `node render.js thumb build/thumb.png`, then save a 1080x1920 version and a
1080x1440 crop.

### Fast edits
If only the last line or the visuals after time T change and earlier timings are identical,
render just the tail with `node render.js video build/tail.mp4 - T`. Then join it after the first
`T*30` frames of the old video (ffmpeg `trim=end_frame` + `concat`) and remux the audio.

## Deliver
`final.mp4`, the thumbnails, and `script.md`. Tell the user they can ask for changes in plain
words ("bigger captions", "lighter skin", "different voice").
