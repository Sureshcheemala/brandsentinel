"""Optional external-AI second opinion on tone. OFF by default.

Enabled only when BS_EXTERNAL_AI=on AND ANTHROPIC_API_KEY is set. It sends the draft text plus the
voice guideline text only (never the brand library, assets or user data). Results are labelled
ai_assisted, always need human judgement, and are never applied automatically.

NOTE: the rules engine is the tested core. This module has not been exercised against the live API
in the build environment; see docs/RESPONSIBLE_AI.md.
"""
import json
import os
import urllib.request

from . import engine


def enabled():
    return os.environ.get("BS_EXTERNAL_AI", "off").lower() == "on" and bool(os.environ.get("ANTHROPIC_API_KEY"))


def status():
    return {
        "enabled": enabled(),
        "provider": "Anthropic API" if enabled() else None,
        "model": os.environ.get("BS_AI_MODEL", "claude-sonnet-5-5") if enabled() else None,
        "sent": "Draft text and the voice guideline text only" if enabled() else "Nothing leaves this server",
    }


def second_opinion(kit, text):
    if not enabled() or not text.strip():
        return []
    guide = next((g for g in kit["guidelines"] if g["id"] == kit["voice"]["guideline"]), None)
    if not guide:
        return []
    prompt = (
        "You review marketing copy against ONE guideline. Reply with JSON only: "
        '{"issues":[{"quote":"exact words from the draft","why":"one sentence"}]}. '
        "Only quote text that appears verbatim. If nothing violates the guideline, return an empty list.\n\n"
        f"Guideline: {guide['text']}\n\nDraft:\n{text[:6000]}"
    )
    body = json.dumps({"model": os.environ.get("BS_AI_MODEL", "claude-sonnet-5-5"), "max_tokens": 600,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        raw = "".join(b.get("text", "") for b in data.get("content", []))
        issues = json.loads(raw[raw.index("{"):raw.rindex("}") + 1]).get("issues", [])
    except Exception:
        return []
    out = []
    src = {"type": "guideline", "id": guide["id"], "title": guide["title"], "excerpt": guide["text"]}
    for i in issues[:5]:
        q = str(i.get("quote", ""))
        pos = text.find(q) if q else -1
        if pos < 0:
            continue  # ignore anything that is not verbatim: no invented evidence
        f = engine.finding("AI-TONE", "tone", "low", pos, pos + len(q), q, str(i.get("why", ""))[:300], src,
                           {"type": "manual", "text": "Consider rewording; this is an AI-assisted opinion."},
                           confidence=0.6, needs_human=True)
        f["ai_assisted"] = True
        out.append(f)
    return out
