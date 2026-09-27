#!/usr/bin/env python3
"""Snowmoon TTS generator (Kokoro jm_kumo, OpenAI-compatible endpoint).

Reads  src/extract.json
Writes tts/chNN_MMMM_<md5[:8]>.mp3   (resume-safe: existing files are skipped)
       tts/manifest.json

Usage:
    TTS_ENDPOINT=http://HOST:PORT/v1/audio/speech  \\
    TTS_MODEL=kokoro TTS_VOICE=jm_kumo             \\
    python3 scripts/gen_tts.py

Defaults match the original build (endpoint/model overridable via env; the LAN
host that produced this dataset is NOT committed for good reason).
"""
import json, re, os, time, threading, random, hashlib
import concurrent.futures as cf
import urllib.request, urllib.error, ssl

ENDPOINT = os.environ.get("TTS_ENDPOINT", "http://127.0.0.1:5001/v1/audio/speech")
MODEL    = os.environ.get("TTS_MODEL", "kokoro")
VOICE    = os.environ.get("TTS_VOICE", "jm_kumo")
CHUNK    = 280          # keep well under the ONNX arena threshold (see PIPELINE.md)
MAXCHUNK = 420
WORKERS  = 2

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC   = os.path.join(ROOT, "src", "extract.json")
TTS   = os.path.join(ROOT, "tts")
LOG   = os.path.join(TTS, "gen.log")
os.makedirs(TTS, exist_ok=True)
_log = open(LOG, "a", buffering=1)
ctx  = ssl.create_default_context()
LOCK = threading.Lock()

def flog(msg):
    with LOCK:
        _log.write(msg + "\n"); _log.flush()

def md5h(s):
    return hashlib.md5(s.encode("utf-8", "ignore")).hexdigest()

def say(text):
    payload = json.dumps({"model": MODEL, "voice": VOICE, "input": text,
                          "response_format": "mp3"}).encode()
    req = urllib.request.Request(ENDPOINT, data=payload,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300, context=ctx) as r:
        return r.read()

def synth(text, fn, depth=0):
    """Write MP3 to fn. Retry x4 on 500; if still failing and depth<10, split the
    text at the midpoint and stitch the two halves (the server's arena attr-vs-
    request-size quirk means bisected halves clear where the whole does not)."""
    for attempt in range(4):
        try:
            d = say(text)
            if len(d) < 300:
                raise ValueError("tiny response (%d)" % len(d))
            tmp = fn + ".part"
            with open(tmp, "wb") as fo:
                fo.write(d)
            os.replace(tmp, fn)
            return os.path.getsize(fn)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None
        except Exception:
            pass
        time.sleep(0.8 * (attempt + 1) + random.random())
    if depth >= 10 or len(text) < 300:
        return None
    half = len(text) // 2
    cut = text.rfind(' ', 0, half + 40)
    if cut <= 0 or cut > half + 40:
        cut = half
    left, right = text[:cut].strip(), text[cut:].strip()
    if len(left) < 20 or len(right) < 20:
        return None
    fnl, fnr = fn + ".A", fn + ".B"
    sza = synth(left, fnl, depth + 1)
    szb = synth(right, fnr, depth + 1)
    if sza and szb:
        with open(fn, "wb") as fo:
            fo.write(open(fnl, "rb").read()); fo.write(open(fnr, "rb").read())
        for x in (fnl, fnr):
            try: os.remove(x)
            except OSError: pass
        return os.path.getsize(fn)
    for x in (fnl, fnr):
        try: os.remove(x)
        except OSError: pass
    return None

def chunkify(text):
    """Sentence-aligned chunks <= CHUNK chars (retained verbatim within the chapter)."""
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, cur = [], ""
    for s in sents:
        cand = (cur + " " + s).strip()
        if len(cand) > CHUNK and cur:
            chunks.append(cur.strip()); cur = s + " "
        else:
            cur = cand + " "
    if cur.strip():
        chunks.append(cur.strip())
    return chunks

def main():
    doc = json.load(open(SRC))
    items = []           # (chap, local_idx, text)
    for i in range(1, 33):
        full = " ".join(doc["chapters"]["chapter-%d" % i]["blocks"])
        for idx, text in enumerate(chunkify(full)):
            items.append((i, idx, text))
    total = len(items)
    flog("=== RUN total=%d CHUNK=%d WORKERS=%d voice=%s ===" % (total, CHUNK, WORKERS, VOICE))

    n_ok, n_fail, n_bytes, failed = 0, 0, 0, []

    def work(item):
        nonlocal n_ok, n_fail, n_bytes
        i, idx, text = item
        fn = "%s/ch%02d_%04d_%s.mp3" % (TTS, i, idx, md5h(text)[:8])
        if os.path.exists(fn) and os.path.getsize(fn) > 300:
            sz = os.path.getsize(fn)
            with LOCK:
                n_ok += 1; n_bytes += sz
            return True
        sz = synth(text, fn)
        if sz:
            with LOCK:
                n_ok += 1; n_bytes += sz
            return True
        with LOCK:
            n_fail += 1
            failed.append((i, idx, len(text)))
        flog("FAIL ch%d#%d len=%d" % (i, idx, len(text)))
        return False

    started = time.time()
    files = []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        fut2it = {ex.submit(work, it): it for it in items}
        for done, fut in enumerate(cf.as_completed(fut2it), 1):
            it = fut2it[fut]
            if fut.result():
                i, idx, text = it
                files.append({"chap": i, "chunk": idx, "file":
                              "%s/ch%02d_%04d_%s.mp3" % (TTS, i, idx, md5h(text)[:8]),
                              "chars": len(text)})
            if done % 50 == 0 or done == total:
                el = time.time() - started
                rate = done / el if el > 1 else 0
                eta = (total - done) / rate if rate else 0
                flog("[%6.0fs] %d/%d  fail=%d  bytes=%.2fMB  rate=%.2f/s  eta=%.1fm"
                     % (el, done, total, n_fail, n_bytes/1048576, rate, eta/60))

    json.dump({"total_requests": total, "succeeded": len(files), "failed": failed,
               "elapsed_seconds": round(time.time()-started, 1), "bytes_total": n_bytes,
               "files": sorted(files, key=lambda x: (x["chap"], x["chunk"]))},
              open(os.path.join(TTS, "manifest.json"), "w"), indent=1)
    flog("FINAL ok=%d/%d failed=%d elapsed=%.1fmin"
         % (len(files), total, n_fail, (time.time()-started)/60))

if __name__ == "__main__":
    main()
