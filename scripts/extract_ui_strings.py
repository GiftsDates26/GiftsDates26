"""Extract every UI string of the GiftsDates frontend for pre-translation.

Outputs /app/backend/ui_strings.json:
  {"dictionary": {key: {lang: text}}, "static": [hardcoded English strings]}
Run:  python /app/scripts/extract_ui_strings.py
"""
import json, re
from pathlib import Path

SRC = Path("/app/frontend/src")
OUT = Path("/app/backend/ui_strings.json")

STR = r'"((?:[^"\\]|\\.)*)"'
PAIR = re.compile(r'(?:"([\w-]+)"|([A-Za-z]{2,3}(?:_[A-Za-z]+)?))\s*:\s*' + STR)
ENTRY = re.compile(r'^\s*(?:"([\w-]+)"|(\w+))\s*:\s*\{(.*)\}\s*,?\s*$')


def unescape(s):
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s.replace('\\"', '"')


def parse_dictionary():
    text = (SRC / "lib/i18n.js").read_text(encoding="utf-8")
    body = text[text.index("const T = {"):]
    d = {}
    for line in body.splitlines():
        m = ENTRY.match(line)
        if not m:
            continue
        key = m.group(1) or m.group(2)
        vals = {}
        for pm in PAIR.finditer(m.group(3)):
            vals[pm.group(1) or pm.group(2)] = unescape(pm.group(3))
        if "en" in vals:
            d[key] = vals
    # multi-line entries fallback (key: {\n ru: "...",\n en: "..." })
    for m in re.finditer(r'^\s*(\w+)\s*:\s*\{\s*\n(.*?)\n\s*\}', body, re.S | re.M):
        key = m.group(1)
        if key in d:
            continue
        vals = {(pm.group(1) or pm.group(2)): unescape(pm.group(3)) for pm in PAIR.finditer(m.group(2))}
        if "en" in vals:
            d[key] = vals
    en_src = SRC / "lib/_en_source.json"
    if en_src.exists():
        for k, v in json.loads(en_src.read_text(encoding="utf-8")).items():
            d.setdefault(k, {}).setdefault("en", v)
    for f in sorted((SRC / "lib/locales").glob("*.json")):
        code = f.stem
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for k, v in data.items():
            if k in d and v and code not in d[k]:
                d[k][code] = v
    return d


HAS_LETTER = re.compile(r"[^\W\d_]", re.U)
JSX_TEXT = re.compile(r">\s*([^<>{}\n`][^<>{}`]*?)\s*(?=<|\{)")
ATTR = re.compile(r'\b(?:placeholder|title|aria-label|label|alt)\s*=\s*"([^"{}]+)"')
TOAST = re.compile(r'toast(?:\.\w+)?\(\s*"([^"]+)"')
JSX_STR = re.compile(r'\{\s*"([^"{}]{2,200})"\s*\}')
CODEY = re.compile(r"(=>|&&|\|\||===|className|\(\)|;\s*$|^[\w.-]+$(?<=_\w))")


def clean(s):
    s = re.sub(r"\s+", " ", s).strip()
    if not (2 <= len(s) <= 400) or not HAS_LETTER.search(s):
        return None
    if CODEY.search(s) or s.startswith(("http", "/", "#", "data-", ")", "!", "]", "[", ";", ",", ".")):
        return None
    if any(x in s for x in ('("', '")', "return (", ".includes(", ".map(", "const ", "?.", "${")):
        return None
    if re.fullmatch(r"[a-z0-9_]+", s) and "_" in s:  # i18n keys / identifiers
        return None
    return s


def parse_static():
    out = set()
    files = [p for p in SRC.rglob("*.jsx") if "/components/ui/" not in str(p)] + [SRC / "App.js"]
    for p in files:
        t = p.read_text(encoding="utf-8")
        for rx in (JSX_TEXT, ATTR, TOAST, JSX_STR):
            for m in rx.finditer(t):
                s = clean(m.group(1))
                if s:
                    out.add(s)
    return sorted(out)


if __name__ == "__main__":
    dictionary = parse_dictionary()
    static = parse_static()
    en_values = {v["en"] for v in dictionary.values()}
    static = [s for s in static if s not in en_values]
    OUT.write_text(json.dumps({"dictionary": dictionary, "static": static}, ensure_ascii=False), encoding="utf-8")
    print(f"dictionary keys: {len(dictionary)}  static strings: {len(static)}  -> {OUT}")
