"""BrandSentinel review engine.

Deterministic, explainable checks. Every finding carries the guideline or approved
fact it relies on, the quoted evidence, a reason and (where possible) a suggested fix.
Nothing here edits content: applying a suggestion is a separate, human-triggered step.
"""
import datetime
import hashlib
import html as htmllib
import io
import re
import struct
import zipfile

HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


class _S:
    def __init__(self, a, b, t):
        self._a, self._b, self._t = a, b, t

    def start(self):
        return self._a

    def end(self):
        return self._b

    def group(self, _=0):
        return self._t


class _Sentences:
    """Splits on . ! ? followed by whitespace/end, and on newlines (so 99.5% stays whole)."""

    @staticmethod
    def finditer(text):
        out, i, n = [], 0, len(text)
        start = 0
        while i < n:
            c = text[i]
            if c == "\n":
                if text[start:i].strip():
                    out.append(_S(start, i, text[start:i]))
                start = i + 1
            elif c in ".!?":
                j = i
                while j + 1 < n and text[j + 1] in ".!?":
                    j += 1
                if j + 1 >= n or text[j + 1].isspace():
                    out.append(_S(start, j + 1, text[start:j + 1]))
                    start = j + 1
                i = j
            i += 1
        if text[start:].strip():
            out.append(_S(start, n, text[start:]))
        return out


SENT = _Sentences
DIRECTIVE = re.compile(r"\[colors:([^\]]*)\]", re.I)


# ----------------------------------------------------------------- helpers
def _guideline(kit, gid):
    for g in kit.get("guidelines", []):
        if g["id"] == gid:
            return {"type": "guideline", "id": gid, "title": g["title"], "excerpt": g["text"]}
    return {"type": "guideline", "id": gid, "title": gid, "excerpt": ""}


def _fact_src(f):
    return {"type": "approved_fact", "id": f["id"], "title": f["source"], "excerpt": f["statement"]}


def _key(rule_id, quote):
    return rule_id + ":" + hashlib.sha1(quote.strip().lower().encode()).hexdigest()[:8]


def finding(rule_id, category, severity, start, end, quote, message, source,
            suggestion=None, confidence=0.95, needs_human=None, extra_id=""):
    if needs_human is None:
        needs_human = confidence < 0.75 or suggestion is None or suggestion.get("type") == "manual"
    return {
        "fid": f"{rule_id}-{start}-{end}{extra_id}",
        "key": _key(rule_id, quote),
        "rule_id": rule_id,
        "category": category,
        "severity": severity,
        "start": start,
        "end": end,
        "quote": quote,
        "message": message,
        "source": source,
        "suggestion": suggestion,
        "confidence": confidence,
        "needs_human": needs_human,
        "ai_assisted": False,
    }


def _word_re(w):
    return re.compile(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", re.I)


def _keyword_present(k, low):
    stem = k.lower().rstrip("s") or k.lower()  # "hours" also matches "hour"
    return re.search(r"\b" + re.escape(stem), low) is not None


def _match_case(original, alt):
    if original[:1].isupper() and alt:
        return alt[:1].upper() + alt[1:]
    return alt


# ----------------------------------------------------------------- colour maths
def _norm_hex(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.upper()


def _rgb(h):
    h = _norm_hex(h).lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminance(h):
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _dist(a, b):
    ra, rb = _rgb(a), _rgb(b)
    return sum((x - y) ** 2 for x, y in zip(ra, rb)) ** 0.5


def nearest_palette(kit, h):
    best = None
    for name, val in kit["visual"]["palette"].items():
        d = _dist(h, val)
        if best is None or d < best[0]:
            best = (d, name, _norm_hex(val))
    return best


# ----------------------------------------------------------------- terminology
def check_terms(kit, text):
    out = []
    for r in kit.get("terminology", []):
        flags = re.I if r.get("ignorecase", True) else 0
        for m in re.finditer(r["pattern"], text, flags):
            if r.get("exact_use") and m.group(0) == r["use"]:
                continue
            use = _match_case(m.group(0), r["use"])
            if r.get("exact_use"):
                use = r["use"]
            out.append(finding(r["id"], "terminology", r.get("severity", "medium"), m.start(), m.end(),
                               m.group(0), r["message"], _guideline(kit, r["guideline"]),
                               {"type": "replace", "text": use}))
    return out


# ----------------------------------------------------------------- voice / tone
def check_voice(kit, text):
    v = kit.get("voice", {})
    src = _guideline(kit, v.get("guideline", "G-VOICE"))
    out = []
    for word, alt in v.get("hype", {}).items():
        for m in _word_re(word).finditer(text):
            out.append(finding("VOICE-HYPE", "tone", "low", m.start(), m.end(), m.group(0),
                               f"'{m.group(0)}' is hype. The brand voice is warm and confident, not exaggerated.",
                               src, {"type": "replace", "text": _match_case(m.group(0), alt)}, confidence=0.9))
    for word, alt in v.get("jargon", {}).items():
        for m in _word_re(word).finditer(text):
            out.append(finding("VOICE-JARGON", "tone", "low", m.start(), m.end(), m.group(0),
                               f"'{m.group(0)}' is business jargon; the voice guideline asks for plain words.",
                               src, {"type": "replace", "text": _match_case(m.group(0), alt)}, confidence=0.85))
    bangs = [m.start() for m in re.finditer(r"!", text)]
    for pos in bangs[v.get("max_exclamations", 1):]:
        out.append(finding("VOICE-EXCLAIM", "tone", "low", pos, pos + 1, "!",
                           "More than one exclamation mark reads as shouting.", src,
                           {"type": "replace", "text": "."}, confidence=0.9))
    for m in re.finditer(r"\b[A-Z]{3,}(?:\s+[A-Z]{2,}\b)+", text):
        if _norm_hex_safe(m.group(0)):
            continue
        out.append(finding("VOICE-CAPS", "tone", "low", m.start(), m.end(), m.group(0),
                           "Runs of capital letters read as shouting and are harder to read.", src,
                           {"type": "replace", "text": m.group(0).capitalize()}, confidence=0.85))
    limit = v.get("max_sentence_words", 28)
    for m in SENT.finditer(text):
        s = m.group(0)
        words = len(re.findall(r"\b[\w'-]+\b", s))
        if words > limit:
            out.append(finding("VOICE-LONG", "tone", "medium", m.start(), m.end(), s.strip(),
                               f"This sentence has {words} words; the guideline limit is {limit}.", src,
                               {"type": "manual", "text": "Split this into two shorter sentences."},
                               confidence=0.8, needs_human=True))
    return out


def _norm_hex_safe(s):
    return bool(HEX.fullmatch(s.strip()))


# ----------------------------------------------------------------- claims
def _numbers(s):
    return [float(x.replace(",", "")) for x in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", s)]


def _expired(f, today):
    try:
        return datetime.date.fromisoformat(f["valid_until"]) < today
    except (KeyError, ValueError):
        return False


# Phrases that look like superlatives but are ordinary wording ("best practices", "best regards").
_NOT_CLAIM = {"best": r"(?!\s+(?:practices?|regards|wishes|efforts?|of luck)\b)"}


def check_claims(kit, text, today):
    out, claims = [], []
    policy = kit.get("claims_policy", {})
    gsrc = _guideline(kit, policy.get("guideline", "G-CLAIMS"))
    for m in SENT.finditer(text):
        s = m.group(0)
        low = s.lower()
        nums = _numbers(s)
        matched = [f for f in kit.get("facts", [])
                   if sum(_keyword_present(k, low) for k in f["keywords"]) >= f.get("min_match", 1)]
        supported_superlative = False
        handled_numeric = False
        for f in matched:
            if not nums:
                continue
            handled_numeric = True
            val = float(f["value"])
            quote = s.strip()
            qs = m.start() + (len(s) - len(s.lstrip()))
            if any(abs(n - val) < 1e-9 for n in nums):
                if _expired(f, today):
                    claims.append({"quote": quote, "status": "outdated", "fact_id": f["id"]})
                    out.append(finding("CLAIM-OUTDATED", "claims", "high", qs, qs + len(quote), quote,
                                       f"This matches '{f['id']}', but that fact expired on {f['valid_until']}. "
                                       "Confirm the current figure with the fact owner before publishing.",
                                       _fact_src(f),
                                       {"type": "manual", "text": f"Check validity of: {f['statement']}"},
                                       confidence=0.9))
                else:
                    claims.append({"quote": quote, "status": "supported", "fact_id": f["id"]})
                    if f.get("allow_superlative"):
                        supported_superlative = True
            else:
                claims.append({"quote": quote, "status": "contradicts", "fact_id": f["id"]})
                out.append(finding("CLAIM-MISMATCH", "claims", "high", qs, qs + len(quote), quote,
                                   f"The figure here differs from approved fact '{f['id']}' "
                                   f"({f['statement']}).",
                                   _fact_src(f), {"type": "manual", "text": f["approved_wording"]},
                                   confidence=0.85))
        if not handled_numeric and re.search(r"\d+(?:\.\d+)?\s?%|\b\d+x\b", s):
            quote = s.strip()
            qs = m.start() + (len(s) - len(s.lstrip()))
            if not any(re.fullmatch(r".*", quote) and c["quote"] == quote for c in claims):
                claims.append({"quote": quote, "status": "unverified", "fact_id": None})
                out.append(finding("CLAIM-UNVERIFIED", "claims", "medium", qs, qs + len(quote), quote,
                                   "This statistic does not match any approved fact. Add an approved source "
                                   "or remove the figure.", gsrc,
                                   {"type": "manual", "text": "No approved fact found for this number."},
                                   confidence=0.7, needs_human=True))
        if not supported_superlative:
            for r in policy.get("risky", []):
                pat = re.compile(r"(?<![\w])" + re.escape(r["phrase"]) + r"(?![\w])" + _NOT_CLAIM.get(r["phrase"], ""), re.I)
                for mm in pat.finditer(s):
                    st = m.start() + mm.start()
                    alt = r.get("alt", "")
                    sug = ({"type": "replace", "text": _match_case(mm.group(0), alt)} if alt
                           else {"type": "manual", "text": "Remove this claim or add an approved source."})
                    out.append(finding("CLAIM-UNSUPPORTED", "claims", r.get("severity", "medium"), st,
                                       st + len(mm.group(0)), mm.group(0),
                                       f"'{mm.group(0)}' is an absolute or ranking claim with no approved "
                                       "supporting fact.", gsrc, sug, confidence=0.7, needs_human=True))
    lowtext = text.lower()
    for d in kit.get("disclaimers", []):
        mm = re.search(d["trigger"], text, re.I)
        if mm and d["text"].lower() not in lowtext:
            out.append(finding(d["id"], "claims", "medium", mm.start(), mm.end(), mm.group(0),
                               f"Offers must carry the standard line '{d['text']}'.",
                               _guideline(kit, d["guideline"]), {"type": "append", "text": d["text"]},
                               confidence=0.9))
            break
    return out, claims


# ----------------------------------------------------------------- accessibility / visual
def _attrs(tag):
    return {k.lower(): v for k, v in re.findall(r"([\w:-]+)\s*=\s*\"([^\"]*)\"", tag)}


def _check_image(kit, alt, src, width, height, start, end, quote, idx):
    out = []
    acc = kit["accessibility"]
    asrc = _guideline(kit, acc["guideline"])
    vsrc = _guideline(kit, kit["visual"]["guideline"])
    base = (src or "").split("/")[-1].split("?")[0].lower()
    if alt is None or (alt.strip() == "" and alt is not None and False):
        out.append(finding("AX-ALT-MISSING", "accessibility", "high", start, end, quote,
                           "This image has no alt text, so screen-reader users get nothing.", asrc,
                           {"type": "manual", "text": "Add an alt attribute that describes the image (or alt=\"\" if purely decorative)."},
                           extra_id=f"-{idx}"))
    elif alt.strip().lower() in acc["weak_alt"] or re.search(r"\.(png|jpe?g|gif|svg)$", alt.strip().lower()):
        out.append(finding("AX-ALT-WEAK", "accessibility", "low", start, end, quote,
                           f"Alt text '{alt}' does not describe the image.", asrc,
                           {"type": "manual", "text": "Describe what the image shows and why it is there."},
                           confidence=0.85, extra_id=f"-{idx}"))
    approved = {a["filename"].lower(): a for a in kit["visual"]["assets"]}
    if "logo" in base and base not in approved:
        out.append(finding("VIS-LOGO-VARIANT", "visual", "high", start, end, quote,
                           f"'{base}' is not an approved logo file.", vsrc,
                           {"type": "manual", "text": "Use logo-primary.svg or logo-mono.svg from the asset library."},
                           extra_id=f"-{idx}"))
    elif base in approved and approved[base]["kind"] == "logo" and width and height:
        ratio = approved[base]["width"] / approved[base]["height"]
        tol = kit["visual"].get("logo_ratio_tolerance", 0.05)
        if abs((width / height) / ratio - 1) > tol:
            out.append(finding("VIS-LOGO-DISTORTED", "visual", "high", start, end, quote,
                               f"The logo is shown at {width}x{height}, which changes its approved proportions.",
                               vsrc, {"type": "manual", "text": f"Keep the ratio {approved[base]['width']}:{approved[base]['height']}."},
                               extra_id=f"-{idx}"))
    return out


def check_access_visual(kit, text, kind):
    out = []
    acc = kit["accessibility"]
    asrc = _guideline(kit, acc["guideline"])
    vsrc = _guideline(kit, kit["visual"]["guideline"])
    idx = 0
    if kind == "html":
        for m in re.finditer(r"<img\b[^>]*>", text, re.I):
            a = _attrs(m.group(0))
            idx += 1
            w = float(a["width"]) if a.get("width", "").replace(".", "", 1).isdigit() else None
            h = float(a["height"]) if a.get("height", "").replace(".", "", 1).isdigit() else None
            out += _check_image(kit, a.get("alt"), a.get("src"), w, h, m.start(), m.end(), m.group(0)[:80], idx)
        for m in re.finditer(r"<a\b[^>]*>(.*?)</a>", text, re.I | re.S):
            label = re.sub(r"<[^>]+>", "", m.group(1)).strip().lower()
            if label in acc["weak_link_text"]:
                out.append(finding("AX-LINK", "accessibility", "low", m.start(), m.end(), m.group(0)[:80],
                                   f"Link text '{label}' does not say where the link goes.", asrc,
                                   {"type": "manual", "text": "Use text that names the destination."},
                                   confidence=0.9))
    else:
        for m in re.finditer(r"!\[([^\]]*)\]\(([^)]*)\)", text):
            idx += 1
            alt = m.group(1)
            out += _check_image(kit, alt if alt.strip() else None, m.group(2), None, None, m.start(), m.end(),
                                m.group(0)[:80], idx)
        for m in re.finditer(r"(?<!!)\[([^\]]+)\]\(([^)]*)\)", text):
            if m.group(1).strip().lower() in acc["weak_link_text"]:
                out.append(finding("AX-LINK", "accessibility", "low", m.start(), m.end(), m.group(0)[:80],
                                   f"Link text '{m.group(1)}' does not say where the link goes.", asrc,
                                   {"type": "manual", "text": "Use text that names the destination."},
                                   confidence=0.9))
    # contrast: html inline styles and [colors: fg=#... bg=#... large] directives
    pairs = []
    if kind == "html":
        for m in re.finditer(r"<[^>]+style\s*=\s*\"([^\"]*)\"[^>]*>", text, re.I):
            st = m.group(1)
            fg = re.search(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3,6})\b", st)
            bg = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6})\b", st)
            fs = re.search(r"font-size\s*:\s*(\d+)px", st)
            if fg and bg:
                pairs.append((m.start(), m.end(), fg.group(1), bg.group(1), bool(fs and int(fs.group(1)) >= 24), m.group(0)[:80]))
    for m in DIRECTIVE.finditer(text):
        fg = re.search(r"fg\s*=\s*(#[0-9a-fA-F]{3,6})", m.group(1))
        bg = re.search(r"bg\s*=\s*(#[0-9a-fA-F]{3,6})", m.group(1))
        if fg and bg:
            pairs.append((m.start(), m.end(), fg.group(1), bg.group(1), "large" in m.group(1).lower(), m.group(0)))
    pal = {_norm_hex(v): n for n, v in kit["visual"]["palette"].items()}
    for s, e, fg, bg, large, q in pairs:
        need = acc["min_contrast_large"] if large else acc["min_contrast"]
        ratio = contrast_ratio(fg, bg)
        if ratio < need:
            fix = None
            for name, val in kit["visual"]["palette"].items():
                if contrast_ratio(val, bg) >= need:
                    if fix is None or contrast_ratio(val, bg) > contrast_ratio(fix[1], bg):
                        fix = (name, val)
            sug = ({"type": "replace_hex", "text": _norm_hex(fix[1]), "target": _norm_hex(fg)}
                   if fix else {"type": "manual", "text": "Choose a palette colour that reaches the required contrast."})
            out.append(finding("AX-CONTRAST", "accessibility", "high", s, e, q,
                               f"Contrast is {ratio:.2f}:1 but {need}:1 is required"
                               f"{' for large text' if large else ''}.", asrc, sug, extra_id=f"-{s}"))
    # palette
    ranges = [(0, len(text))] if kind == "html" else [(m.start(), m.end()) for m in DIRECTIVE.finditer(text)]
    seen = set()
    for a, b in ranges:
        for m in HEX.finditer(text[a:b]):
            s, e = a + m.start(), a + m.end()
            h = _norm_hex(m.group(0))
            if h in pal or (s, e) in seen:
                continue
            seen.add((s, e))
            d, name, near = nearest_palette(kit, h)
            out.append(finding("VIS-PALETTE", "visual", "medium" if d > 40 else "low", s, e, m.group(0),
                               f"{m.group(0)} is not in the brand palette; nearest approved colour is "
                               f"{name} ({near}).", vsrc, {"type": "replace", "text": near},
                               confidence=0.9, extra_id=f"-{s}"))
    return out


# ----------------------------------------------------------------- document / image ingest
def extract_docx(data):
    """Return (text, extra_findings). Reads word/document.xml with the standard library only."""
    z = zipfile.ZipFile(io.BytesIO(data))
    if "word/document.xml" not in z.namelist():
        raise ValueError("Not a valid .docx file")
    xml = z.read("word/document.xml").decode("utf8", "ignore")
    body = re.sub(r"</w:p>", "\n", xml)
    body = re.sub(r"<w:tab/>", "\t", body)
    body = re.sub(r"<[^>]+>", "", body)
    text = htmllib.unescape(body).strip()
    extra = []
    for i, m in enumerate(re.finditer(r"<wp:docPr\b[^>]*>", xml), 1):
        a = _attrs(m.group(0))
        descr = (a.get("descr") or "").strip()
        if not descr:
            extra.append({"rule_id": "AX-ALT-MISSING", "image_index": i})
    return text, extra


def docx_extra_findings(kit, extra):
    out = []
    asrc = _guideline(kit, kit["accessibility"]["guideline"])
    for e in extra:
        out.append(finding("AX-ALT-MISSING", "accessibility", "high", -1, -1, f"Image {e['image_index']} in the document",
                           "This image has no alt text, so screen-reader users get nothing.", asrc,
                           {"type": "manual", "text": "Add a description in Word: right-click the image, Edit Alt Text."},
                           extra_id=f"-img{e['image_index']}"))
    return out


def image_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
    m = re.search(rb"<svg[^>]*\bwidth=\"([\d.]+)\"[^>]*\bheight=\"([\d.]+)\"", data[:2000])
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def review_image(kit, filename, data, alt):
    out = []
    size = image_size(data)
    base = filename.lower()
    quote = filename
    out += _check_image(kit, alt if (alt or "").strip() else None, filename,
                        size[0] if size else None, size[1] if size else None, -1, -1, quote, 1)
    if size:
        minw = kit["visual"].get("min_image_width", 0)
        approved = {a["filename"].lower(): a for a in kit["visual"]["assets"]}
        if base not in approved and size[0] < minw and "logo" not in base:
            out.append(finding("VIS-RESOLUTION", "visual", "low", -1, -1, quote,
                               f"Image is {size[0]}px wide; the visual guideline asks for at least {minw}px.",
                               _guideline(kit, kit["visual"]["guideline"]),
                               {"type": "manual", "text": "Use a larger source image."}, confidence=0.9))
    elif base.endswith((".png", ".jpg", ".jpeg")):
        out.append(finding("VIS-UNREADABLE", "visual", "low", -1, -1, quote,
                           "Image dimensions could not be read.", _guideline(kit, kit["visual"]["guideline"]),
                           None, confidence=0.5))
    return out


# ----------------------------------------------------------------- entry point
SEV = {"high": 3, "medium": 2, "low": 1}


def review(kit, kind, text, today=None):
    """Review text content. kind: text | markdown | html."""
    today = today or datetime.date.today()
    found = []
    # For HTML, wording checks run on visible text; tags are blanked out so offsets still line up.
    vis = re.sub(r"<[^>]*>", lambda m: " " * len(m.group(0)), text) if kind == "html" else text
    found += check_terms(kit, vis)
    found += check_voice(kit, vis)
    cl, claims = check_claims(kit, vis, today)
    found += cl
    found += check_access_visual(kit, text, kind)
    seen, uniq = set(), []
    for f in found:
        if f["fid"] in seen:
            continue
        seen.add(f["fid"])
        uniq.append(f)
    uniq.sort(key=lambda f: (f["start"] if f["start"] >= 0 else 10 ** 9, -SEV[f["severity"]]))
    return {"findings": uniq, "claims": claims}


def apply_suggestion(text, f):
    """Return new text with the finding's suggestion applied, or raise ValueError."""
    sug = f.get("suggestion") or {}
    t = sug.get("type")
    if t == "replace":
        if text[f["start"]:f["end"]] != f["quote"]:
            raise ValueError("Text has changed since this finding was produced")
        return text[:f["start"]] + sug["text"] + text[f["end"]:]
    if t == "replace_hex":
        seg = text[f["start"]:f["end"]]
        if sug["target"].lower() not in _norm_hex_text(seg):
            raise ValueError("Text has changed since this finding was produced")
        new = re.sub(re.escape(sug["target"]), sug["text"], seg, flags=re.I)
        if new == seg:
            short = "#" + "".join(c for c in sug["target"].lstrip("#")[::2])
            new = re.sub(re.escape(short), sug["text"], seg, flags=re.I)
        return text[:f["start"]] + new + text[f["end"]:]
    if t == "append":
        return text.rstrip() + "\n" + sug["text"] + "\n"
    raise ValueError("This suggestion needs a human edit; it cannot be applied automatically")


def _norm_hex_text(seg):
    return " ".join(_norm_hex(h).lower() for h in HEX.findall(seg)) + " " + seg.lower()
