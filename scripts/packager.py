#!/usr/bin/env python3
"""Concat per-chapter TTS chunks into 32 tagged chapter MP3s + playlist + manifest.

Reads  tts/ch*.mp3  (grouped by chNN_ file prefix, in chunk order)
Writes audio/chNN.mp3  (ID3-tagged, 24kHz mono 64kbps)
       audio/Snowmoon.m3u
       audio/manifest.json

Why re-encode (not stream-copy): ffmpeg 6.x refuses to INSERT ID3 tags into an MP3
with `-c:a copy` ("Invalid argument" muxer error). Re-encoding to libmp3lame
(Mod IV) + -metadata is the reliable path.
"""
import os, re, glob, json, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTS  = os.path.join(ROOT, "tts")
OUT  = os.path.join(ROOT, "audio")
(os.makedirs(OUT, exist_ok=True) if False else None)
pass

ALBUM, ARTIST, GENRE, DATE = "Snowmoon", "Vitalik Buterin", "Audiobook", "2026"

def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)
def dur(p):
    r = sh("ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "csv=p=0", p)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0

def build():
    bychap = {}
    for f in sorted(glob.glob(os.path.join(TTS, "ch*_*.mp3"))):
        m = re.match(r"ch([0-9]+)_", os.path.basename(f))
        if m:
            bychap.setdefault(int(m.group(1)), []).append(f)
    chapters = sorted(bychap)
    total = 0.0
    m3u = []
    for c in chapters:
        files = sorted(bychap[c])
        out = os.path.join(OUT, "ch%02d.mp3" % c)
        lst = out + ".list"
        with open(lst, "w") as fh:
            for f in files:
                fh.write("file '%s'\n" % f)
        r = sh("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
               "-c:a", "libmp3lame", "-b:a", "128k", out)
        if r.returncode:
            print("concat FAIL ch %d: %s" % (c, r.stderr[-400:])); continue
        # re-encode to attach ID3 (copy won't insert)
        tmp = os.path.join(OUT, "ch%02d_tagged.mp3" % c)
        r2 = sh("ffmpeg", "-y", "-i", out, "-map_metadata", "-1",
                "-metadata", "album=%s" % ALBUM,
                "-metadata", "artist=%s" % ARTIST,
                "-metadata", "title=Chapter %d" % c,
                "-metadata", "track=%d" % c,
                "-metadata", "date=%s" % DATE,
                "-metadata", "genre=%s" % GENRE,
                "-ar", "24000", "-ac", "1", "-b:a", "64k",
                "-c:a", "libmp3lame", tmp)
        if r2.returncode:
            print("tag FAIL ch %d: %s" % (c, r2.stderr[-400:]))
        else:
            os.replace(tmp, out)
        os.remove(lst)
        d = dur(out)
        total += d
        m3u.append((c, d))
        print("ch%02d  %.2f min" % (c, d / 60))
    with open(os.path.join(OUT, "Snowmoon.m3u"), "w") as fh:
        fh.write("#EXTM3U\n")
        for c, d in m3u:
            fh.write("#EXTINF:%.0f, Snowmoon - Chapter %d\n" % (d, c))
            fh.write("ch%02d.mp3\n" % c)
    json.dump({"chapters": [c for c, _ in m3u],
               "total_seconds": round(total, 1),
               "total_minutes": round(total / 60, 1),
               "bitrate": "64 kbps (24 kHz mono)",
               "voices": "Kokoro jm_kumo",
               "source": "https://vitalik.eth.limo/snowmoon/",
               "license": "GPL-3.0"},
              open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
    print("packed %d chapters, %.1f min" % (len(m3u), total / 60))

if __name__ == "__main__":
    build()
