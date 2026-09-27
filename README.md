# Snowmoon — Audiobook (jm_kumo voice)

A complete TTS-rendered audiobook of ["Snowmoon"](https://vitalik.eth.limo/snowmoon/) by
**Vitalik Buterin**, rendered with **Kokoro**'s Japanese male voice
[`jm_kumo`](https://github.com/thewh1teagle/kokoro/blob/main/README.md) from the
OpenAI-compatible TTS endpoint on a private LAN (host intentionally not committed).

- **Length:** 32 chapters, **667 min (~11 h 07 min)** total.
- **Codec:** MP3 @ 64 kbps, 24 kHz mono, ID3v2.4 tagged (`album=Snowmoon`, `artist=Vitalik Buterin`,
  `track=<absolute chapter number 1..32>`, `title=Chapter NN`, `genre=Audiobook`, `date=2026`).
- **Total size:** ~303 MB of audio across the 32 chapter MP3s.

> Note on the voice: `jm_kumo` is a *Japanese* voice. On English it produces a clean,
> soft-accented cadence. This is intentional per the audio production brief.

---

## License

**GNU General Public License, version 3** (see the [`LICENSE`](LICENSE) file — the
unmodified gpl3 text). Note: *not* CC-BY-SA, per the author's intentional choice.

The audiobook is a **derivative work** of the Snowmoon text, so the same license
applies to it. In particular the upstream author's own declaration on the source
page (["Snowmoon", declarations](https://vitalik.eth.limo/snowmoon/), captured verbatim
in [`upstream_declarations.txt`](upstream_declarations.txt)):

> *Snowmoon is released under the GPL v3.*
> *Yes, I said GPL v3, not CC-BY-SA. My legal theory, which Kimi K3 says is plausible, is
> that you are free to go turn it into a movie or a vibe-coded anime or whatever, but if
> you do that, you are required to open-source the pipeline (AI prompts, scripts,
> task-specific harness, etc) and other non-commodity materials that you used to make it
> so that other people can build on top of your work.*

By that theory — extended here to the audiobook as a derivative — **this repo already
satisfies the pipeline-open-source clause**: see [`scripts/`](scripts/) for the
extractor and generation pipeline, and [`PIPELINE.md`](PIPELINE.md) for complete
step-by-step reconstruction.

### Authorship declaration (carried forward from the upstream)

- *All words were written directly by me* — Vitalik Buterin.
- *Spelling, grammar and style checking, verifying consistency of the rules of Minpentai
  and Dzegoban, the HTML and CSS format and style, and the SVGs were done with assistance
  from Kimi K3 and Qwen 3.8 Flash Next.* *(i.e. the raw text was human-authored.)*
- The *audiobook* was produced end to end by **Hermes Agent**, driven by
  **Qwen3.8-27B-exl3-5bpw** served on ExLlama's **Tabby API**. No LLM altered,
  summarised, or re-wrote a single word of the source text: the
  agent extracted the prose, drove the `jm_kumo` TTS endpoint, and packaged the
  result per the pipeline documented in `PIPELINE.md`. (Kokoro is MIT-licensed
  and is the decoder that actually produces the waveform.)

### Cross-licensing note (GPL-3.0 vs source text style)

If you make a further derivative of this audiobook (e.g. adapt it to another voice, re-do
the rendering, translate it, or embed it in an app), your resulting whole is subject to
GPL-3.0. The specific interactions are:

- You **may** do whatever GPL-3.0 permits (see [§13 remote offering](https://www.gnu.org/licenses/gpl-3.0.en.html#section13)
  and [*Free Software Foundation FAQ*](https://gnu.org/licenses/gpl-faq.html)).
- You **must** preserve: the LICENSE, this notice, and the upstream declarations.
- You **must not** impose additional restrictions (§7 forbids that).
- If a downstream monetization path (movie, paid app, commercial re-voice, etc.) is used,
  the upstream "pipeline open-source" clause still applies per the academic legal theory
  quoted above.

---

## Using the audiobook (Android, phone)

**Recommended app (free, open source):** **VLC for Android** — F‑Droid, package id
`org.videolan.vlc`. Alternative: **Sound** from F‑Droid (`app.soundcenter.player`).

Steps (VLC):

1. Clone or download this repo and copy the `audio/` folder to your device.
   (It is 303 MB of audio; individual chapters are each a few MB so you can copy
   just the ones you want — they are self-contained.)
2. Open VLC → **Media → Songs**.
3. A single album **"Snowmoon"** appears with 32 tracks (Chapters 1‑32). Tap to play;
   sleep timer and resume are built in.

Alternatively, open `audio/Snowmoon.m3u` with any m3u-capable player (the relative
paths inside resolve against the same folder the m3u lives in).

### Per-chapter files

Each chapter is an individual MP3 (`audio/ch01.mp3` … `audio/ch32.mp3`) with its own
ID3 track number, so any player can jump to a chapter, mark a spot, or copy a single
chapter (largest is ~14 MB).

---

## Rebuilding from source (no pre-built audio)

If you'd rather regenerate from the source:

1. See [`scripts/`](scripts/) and
   [`PIPELINE.md`](PIPELINE.md) for a documented multi-step reproduction; the
   pipeline is idempotent and md5-cached, so re-runs only re-synthesize chunks
   that aren't present.
2. Requires a working Kokoro OpenAI‑compatible TTS endpoint at your LAN
   (see the host lineage in `PIPELINE.md`). The original host used was
   the exact address is not committed. Reconstruct from the Pipeline doc; the TTS host lineage is any Kokoro server serving OpenAI-compatible `/v1/audio/speech`.

---

## Contents of this repo

```
LICENSE                             # GNU GPL-3.0 (36 KB, canonical text)
upstream_declarations.txt           # Copy of the source-page license + AI declarations
README.md                           # this file
PIPELINE.md                         # Step-by-step rebuild guide (TTS + packaging)
scripts/
  extract_snowmoon.py               # HTML → 99,144 word per-chapter block corpus
  gen_tts.py                        # Sentence-chunked TTS driver (280 char chunks,
                                    #   2-wide, 500-error auto-shrink, md5-file resume)
  packager.py                       # Concat chunks → 32 chapter MP3s + ID3v2 tags + m3u
src/
  chapters/chapter-1.html .. chapter-32.html     # upstream source, verbatim
  extract.json                          # paragraph-ordered corpus: 4,519 blocks, 99,144 words
audio/
  ch01.mp3 .. ch32.mp3              # 64 kbps / 24 kHz mono, ID3v2.4, atomable
  Snowmoon.m3u                           # full-book playlist (relative paths)
  manifest.json                          # machine-readable metadata: chapters, totals, voices
```

## To reproduce

```
scripts/extract_snowmoon.py   # reads src/chapters/, writes src/extract.json
scripts/gen_tts.py            # reads src/extract.json, writes tts/ch*.mp3
scripts/packager.py           # reads tts/ch*.mp3, writes audio/ch*.mp3 + m3u
```

## Source

- Text: <https://vitalik.eth.limo/snowmoon/> (fetched 2026-09-27, GPL-3.0).
- Kokoro voice + model: <https://github.com/thewh1teagle/kokoro>, `jm_kumo`
  variant (Japanese male, 24 kHz mono).
- TTS host lineage: an on-LAN Kokoro server (OpenAI-compatible)/`/v1/audio/speech`.
  The host address is intentionally not committed. Cross-licensing note: should a
  third party operate an endpoint compatible with Kokoro's request schema, they own
  the deployed copy of Kokoro; this repo remains unmodified.