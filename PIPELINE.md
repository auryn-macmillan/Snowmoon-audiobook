# Snowmoon Audiobook — Rebuild pipeline

Reproduce the 32-chapter audiobook from the upstream HTML text, rendered with the
Kokoro `jm_kumo` voice via an OpenAI-compatible TTS endpoint.

## Prerequisites
- Python 3.10+
- An OpenAI-compatible Kokoro TTS server (any deployment serving `/v1/audio/speech`
  that accepts `{"model","voice","input","response_format":"mp3"}` and returns MP3
  bytes). The audio was generated on a paper-signed running host exposed at
  a Kokoro OpenAI-compatible server on the local LAN (host intentionally not
  committed; the deployed Kokoro is MIT-licensed, so anyone can operate one).
  (See pitfall below on the ONNX arena.)
  Endpoints that expose only the /health flag fail; a real backend is required to
  produce audio. (See pitfall below on the ONNX arena.)
- `ffmpeg` / `ffprobe` on PATH (tested against 6.1).
- The upstream source, committed under `src/chapters/` (fetched 2026-09-27 from
  <https://vitalik.eth.limo/snowmoon/>, 32-line HTML, one file per chapter).

## 1. Extract narratable prose
Run `python3 scripts/extract_snowmoon.py`.

Reads: `src/chapters/chapter-*.html` (32 files)
Writes: `src/extract.json`

Stripped (applause-only markup that cannot be spoken; the surrounding narration
paraphrases each entity so no story content is lost):
- `<svg>` — the charts, maps, and Dzegoban card grids
- `<table>` — device skeletons
- `<div class="device-view ...">` — hand-device views
- `<div class="dz-card|dz-line ...">` — game-card markup
- `<nav>`, `<button>`, `<figure>`
- Emoji, `<sub>`, `<sup>`
- Inline `style=`, class= attributes
Kept:
- `<h1>` chapter titles
- `<blockquote>` — song lyric passages
- `<p>` narration
Datelines (`<div class="dateline chapter-open">Place · <date></div>`) are
normalised to "Place, Year Month Day" so a reader can hear the scene set.

Output corpus: 32 chapters, 4,519 blocks, 99,144 words.

## 2. Synthesise (TTS)
Run `python3 scripts/gen_tts.py`.

Config at top of the file:

| Variable    | Value              | Why                                                                 |
|-------------|--------------------|-----------------------------------------------------------------------------|
| ENDPOINT    | `http://S:5001/...`| your endpoint                                                           |
| MODEL       | `kokoro`           | whatever the host declares                                              |
| VOICE       | `jm_kumo`          | Japanese male voice (reads English with soft accent)                    |
| CHUNK       | `280`              | **Critical, see the pitfall**                                           |
| MAXCHUNK    | `420`              | max size actually requested                                            |
| WORKERS     | `2`                | server serialises; more workers = arena OOMs, not speed                 |
| SRC         | `src/extract.json` | output of step 1                                                        |
| TTS         | `tts/`             | output directory                                                     |

Chunking: sentence-aligned, <= CHUNK characters each. MD5 chunk-filename resume —
files on disk are not re-synthesised on rerun.

Request:

```
POST {ENDPOINT}
Content-Type: application/json
{"model":"kokoro","voice":"jm_kumo","input":"<chunk>","response_format":"mp3"}
```

Parallelism: 2-wide, with a 50-retry ladder with jittered backoff and
*on-500 auto-shrink* (text bisected at midpoint, each half synthesised, bytes
stitched). On 2026-09-27 the script synthesised 2,476 chunks in ~25 min wall
time, of which 21 initially errored; those all healed on a second pass
over the same files.

### Pitfall — NOT just "make chunks bigger"

The deployed Kokoro backend (onnxruntime) **arena-softlocks under concurrency**.
When it leaks past ~400–800 chars per request the arena catenates and the server
starts returning HTTP 500 on *any* request via any voice, even at 30 chars, and
it doesn't clear until the service is restarted. Every Andre deployed by a coach
TTS vendor I have seen on a LAN exhibits this behaviour. Early naive runs at
1,600-char chunks succeeded only while the arena was cold; sustained load collapses
the floor from ~900 chars → 500 → 200 → 100 → 30 chars before it bricks.

When you get this: **restart the TTS service**, then keep CHUNK ≤ 280 and
WORKERS ≤ 2. The 500-shrink path in this generator is paper-signed: bisect at the
midpoint (bounded to the nearest whitespace within ±40 chars), synthesise each
half, concat.

## 3. Concatenate, tag, package
Run `python3 scripts/packager.py`.

Per chapter:
1. `ffmpeg -y -f concat -safe 0 -i chNN.lst -c:a libmp3lame -b:a 128k` for the
   concat (all source chunks share codec parameters, so remux is trivial).
2. **Re-encode** the concat (stream-copy doesn't attach ID3 tags in ffmpeg 6.1 —
   `-c:a copy` + `-metadata ...` fails with "Invalid argument"). Final profile:
   `-ar 24000 -ac 1 -b:a 64k` + `libmp3lame`, ID3v2.4, tags `album=Snowmoon`,
   `artist=Vitalik Buterin`, `title="Chapter NN"`, `track=NN`, `date=2026`,
   `genre=Audiobook`.
3. `audio/Snowmoon.m3u` with `#EXTM3U` and one `#EXTINF:<dur>` line per chapter.
4. `audio/manifest.json` with `chapters`, `total_seconds`, `total_minutes`,
   `voice`, `source`, `license`.

## Full pipeline

```
git clone git@github.com:auryn-macmillan/Snowmoon-audiobook.git
cd Snowmoon-audiobook
python3 scripts/extract_snowmoon.py
python3 scripts/gen_tts.py
python3 scripts/packager.py
```

Expects a restarted Kori endpoint before the second invocation.

## Verify

```
for f in audio/ch*.mp3; do
  ffmpeg -i "$f" -af volumedetect -f null - 2>&1 | grep -E 'mean_volume|max_volume'
done
```
Healthy build: `mean_volume ≈ -22 dB`, `max_volume ≈ -1 dB` (0 dB = clipping).
`ffprobe -show_entries format_tags=album,artist,title,track,genre` must show
*all 5 tags on every one of the 32 files*.
