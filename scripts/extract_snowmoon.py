#!/usr/bin/env python3
"""Strip Snowmoon chapter HTML to narratable prose.

Reads  src/chapters/chapter-1.html .. chapter-32.html
Writes src/extract.json  -> {"order":[1..32], "chapters":{"chapter-N":{"blocks":[...]}}}

Apparatus that an audiobook cannot speak is removed (each is referenced nearby in
prose, so nothing is lost): svg, table, div.device-view, div.dz-*, nav, button,
figure. Emoji / sub / sup are removed; the rest is plain narration.
Paragaphs in chapter-order are preserved as one block per <p>.
"""
import re, html as H, json, os

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "chapters")
OUT = os.path.join(os.path.dirname(__file__), "..", "src", "extract.json")

def cut_span(text, open_tag_regex):
    """Remove every matched open tag plus its balanced sibling tokens."""
    out, i = [], 0
    while True:
        m = re.search(open_tag_regex, text[i:])
        if not m:
            out.append(text[i:]); break
        o_start, o_end = i + m.start(), i + m.end()
        out.append(text[i:o_start])
        tag = re.match(r'<([a-zA-Z][a-zA-Z0-9]*)', text[o_start:o_end]).group(1).lower()
        j, depth = o_end, 1
        while depth > 0:
            no = re.search(r'<%s[\s>]' % tag, text[j:])
            nc = re.search(r'</%s\s*>' % tag, text[j:])
            cand = []
            if no: cand.append(('o', j + no.start()))
            if nc: cand.append(('c', j + nc.start()))
            if not cand:
                break
            kind, pos = min(cand, key=lambda x: x[1])
            j = pos + (len(tag) + 3 if kind == 'c' else len(tag) + 1)
            depth += (1 if kind == 'o' else -1)
        out.append(' ')
        i = j
    return ''.join(out)

EMO = re.compile(
    '[\U0001F000-\U0001FAFF\u2600-\u27BF\u263A-\u2648\u2764\u274C\u2714\uFE0F\uFE0E]')

def prose(path):
    raw = open(path, encoding='utf-8').read()
    body = raw[raw.find('<h1'):]
    body = cut_span(body, r'<svg\b[^>]*?/?>')
    body = cut_span(body, r'<table\b[^>]*>')
    body = cut_span(body, r'<figure\b[^>]*>')
    body = cut_span(body, r'<div\b[^>]*class="[^"]*(?:device-view|dz-)[^"]*"[^>]*>')
    body = re.sub(r'<nav\b[^>]*>.*?</nav\s*>', ' ', body, flags=re.S)
    body = cut_span(body, r'<button\b[^>]*>')
    body = re.sub(r'<style.*?</style>', ' ', body, flags=re.S)
    body = re.sub(r'<h1[^>]*>', '\n# ', body)
    body = re.sub(r'</?blockquote>', '\n', body)
    body = re.sub(r'<br\s*/?>', '\n', body)
    body = re.sub(r'</?p>', '\n', body)
    body = re.sub(r'<[^>]+>', '', body)
    body = H.unescape(body)
    body = EMO.sub('', body)
    lines = []
    for ln in body.split('\n'):
        ln = re.sub(r'\s+', ' ', ln).strip().lstrip('#').strip()
        if ln:
            lines.append(ln)
    return lines

def main():
    src = os.path.normpath(SRC)
    chapters = {}
    for c in range(1, 33):
        fp = os.path.join(src, 'chapter-%d.html' % c)
        chapters['chapter-%d' % c] = {'blocks': prose(fp)}
    json.dump({'order': list(range(1, 33)), 'chapters': chapters},
              open(os.path.normpath(OUT), 'w'), ensure_ascii=False)
    tw = sum(len(x.split()) for v in chapters.values() for x in v['blocks'])
    tb = sum(len(v['blocks']) for v in chapters.values())
    print('extracted %d blocks, %d words -> %s' % (tb, tw, OUT))

if __name__ == '__main__':
    main()
