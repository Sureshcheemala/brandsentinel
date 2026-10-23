"""BrandSentinel HTTP server (standard library only): REST API + static single-page UI."""
import base64
import collections
import difflib
import json
import mimetypes
import os
import re
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import db, engine, llm

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_BODY = 6 * 1024 * 1024
MAX_IMAGE = 4 * 1024 * 1024
KINDS = {"text", "markdown", "html", "docx", "image"}
IMG_EXT = (".png", ".jpg", ".jpeg", ".svg")
ROLES_REVIEW = {"reviewer", "manager", "admin"}
FAILED = collections.defaultdict(list)  # username -> failure timestamps (login throttle)
ROUTES = []


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


def route(method, pattern):
    rx = re.compile("^" + re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", pattern) + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn
    return deco


# ------------------------------------------------------------------ helpers
def now():
    return time.time()


def audit(c, user, action, item_id=None, detail=""):
    c.execute("INSERT INTO audit(ts,user_id,action,item_id,detail) VALUES(?,?,?,?,?)",
              (now(), user["id"] if user else None, action, item_id, detail[:500]))


def need(cond, status, msg):
    if not cond:
        raise ApiError(status, msg)


def get_item(c, item_id):
    row = c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    need(row, 404, "Item not found")
    return row


def can_view(user, item):
    if user["role"] in ("manager", "admin"):
        return True
    if item["owner_id"] == user["id"]:
        return True
    return user["role"] == "reviewer" and item["status"] != "draft"


def user_name(c, uid):
    r = c.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
    return r["name"] if r else "system"


def dismissed_map(c, item_id):
    rows = c.execute("SELECT key,reason,user_id,rev_n FROM events WHERE item_id=? AND action='dismissed'",
                     (item_id,)).fetchall()
    return {r["key"]: r for r in rows}


def annotate(c, item_id, findings):
    dm = dismissed_map(c, item_id)
    for f in findings:
        d = dm.get(f["key"])
        f["status"] = "dismissed" if d else "open"
        if d:
            f["dismiss_reason"] = d["reason"]
            f["dismissed_by"] = user_name(c, d["user_id"])
    return findings


def run_review(c, item, kind, content, blob=None, meta=None):
    kit_version, kit = db.latest_kit(c)
    ai = False
    if kind == "image":
        findings = engine.review_image(kit, meta["filename"], blob, meta.get("alt", ""))
        claims = []
    else:
        ek = "html" if kind == "html" else ("markdown" if kind == "markdown" else "text")
        res = engine.review(kit, ek, content)
        findings, claims = res["findings"], res["claims"]
        if kind == "docx":
            findings += engine.docx_extra_findings(kit, json.loads(item["extra_json"] or "[]"))
        extra = llm.second_opinion(kit, content)
        if extra:
            ai = True
            findings += extra
    return findings, claims, kit_version, ai


def add_revision(c, item, user, kind, content, note, blob=None, meta=None):
    n = c.execute("SELECT COALESCE(MAX(n),0)+1 FROM revisions WHERE item_id=?", (item["id"],)).fetchone()[0]
    findings, claims, kv, ai = run_review(c, item, kind, content, blob, meta)
    c.execute("""INSERT INTO revisions(item_id,n,content,meta_json,findings_json,claims_json,kit_version,created_by,
                 ts,note,ai_used,blob) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
              (item["id"], n, content, json.dumps(meta or {}), json.dumps(findings), json.dumps(claims), kv,
               user["id"], now(), note, int(ai), blob))
    c.execute("UPDATE items SET updated=? WHERE id=?", (now(), item["id"]))
    return n


def latest_rev(c, item_id):
    return c.execute("SELECT * FROM revisions WHERE item_id=? ORDER BY n DESC LIMIT 1", (item_id,)).fetchone()


def rev_view(c, item, r):
    findings = annotate(c, item["id"], json.loads(r["findings_json"]))
    return {"n": r["n"], "content": r["content"], "meta": json.loads(r["meta_json"] or "{}"), "findings": findings,
            "claims": json.loads(r["claims_json"] or "[]"), "kit_version": r["kit_version"], "note": r["note"],
            "ai_used": bool(r["ai_used"]), "by": user_name(c, r["created_by"]), "ts": r["ts"]}


def open_counts(findings):
    out = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        if f["status"] == "open":
            out[f["severity"]] += 1
    return out


def item_summary(c, row):
    r = latest_rev(c, row["id"])
    f = annotate(c, row["id"], json.loads(r["findings_json"]))
    return {"id": row["id"], "title": row["title"], "kind": row["kind"], "status": row["status"],
            "owner": user_name(c, row["owner_id"]), "owner_id": row["owner_id"], "updated": row["updated"],
            "revision": r["n"], "open": open_counts(f)}


def item_detail(c, row, user):
    revs = c.execute("SELECT n,note,created_by,ts,ai_used FROM revisions WHERE item_id=? ORDER BY n", (row["id"],)).fetchall()
    latest = rev_view(c, row, latest_rev(c, row["id"]))
    comments = [{"id": x["id"], "rev": x["rev_n"], "fid": x["fid"], "by": user_name(c, x["user_id"]), "body": x["body"],
                 "ts": x["ts"]} for x in c.execute("SELECT * FROM comments WHERE item_id=? ORDER BY id", (row["id"],))]
    events = [{"rev": x["rev_n"], "rule": x["rule_id"], "action": x["action"], "reason": x["reason"],
               "by": user_name(c, x["user_id"]), "ts": x["ts"]}
              for x in c.execute("SELECT * FROM events WHERE item_id=? ORDER BY id", (row["id"],))]
    s = item_summary(c, row)
    s.update({"latest": latest, "comments": comments, "events": events,
              "revisions": [{"n": r["n"], "note": r["note"], "by": user_name(c, r["created_by"]), "ts": r["ts"],
                             "ai_used": bool(r["ai_used"])} for r in revs],
              "can_edit": row["owner_id"] == user["id"] and row["status"] in ("draft", "changes_requested"),
              "ai": llm.status()})
    return s


def edit_allowed(user, item):
    need(item["owner_id"] == user["id"], 403, "Only the owner can edit this item")
    need(item["status"] in ("draft", "changes_requested"), 409, "Item is locked while in review, approved or published")


# ------------------------------------------------------------------ auth & session
@route("POST", "/api/login")
def login(ctx):
    u = str(ctx.body.get("username", "")).strip().lower()
    recent = [t for t in FAILED[u] if now() - t < 300]
    FAILED[u] = recent
    need(len(recent) < 5, 429, "Too many failed attempts. Try again in a few minutes.")
    row = ctx.c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
    ok = row and secrets.compare_digest(db.hash_pw(str(ctx.body.get("password", "")), row["salt"]), row["pw_hash"])
    if not ok:
        FAILED[u].append(now())
        raise ApiError(401, "Wrong username or password")
    token = secrets.token_hex(24)
    ctx.c.execute("INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)", (token, row["id"], now() + 8 * 3600))
    audit(ctx.c, row, "login")
    return 200, {"token": token, "user": {"id": row["id"], "name": row["name"], "role": row["role"], "team": row["team"]}}
login.public = True


@route("GET", "/api/me")
def me(ctx):
    u = ctx.user
    return 200, {"id": u["id"], "name": u["name"], "role": u["role"], "team": u["team"]}


@route("GET", "/api/disclosure")
def disclosure(ctx):
    return 200, {"ai": llm.status(),
                 "storage": "All content, brand kit and audit data are stored in a local SQLite file on this server.",
                 "automation": "Findings are produced by a rules engine. Suggestions are never applied without a person clicking Accept.",
                 "external_services": ["Anthropic API (optional, off by default)"] if llm.enabled() else []}
disclosure.public = True


@route("GET", "/api/health")
def health(ctx):
    return 200, {"ok": True, "service": "brandsentinel"}
health.public = True


# ------------------------------------------------------------------ brand kit
@route("GET", "/api/brandkit")
def get_kit(ctx):
    v, kit = db.latest_kit(ctx.c)
    return 200, {"version": v, "kit": kit}


@route("PUT", "/api/brandkit")
def put_kit(ctx):
    need(ctx.user["role"] == "admin", 403, "Only an admin can change the brand kit")
    kit = ctx.body.get("kit")
    need(isinstance(kit, dict), 400, "kit must be an object")
    for k in ("guidelines", "terminology", "voice", "facts", "claims_policy", "disclaimers", "accessibility", "visual"):
        need(k in kit, 400, f"kit is missing '{k}'")
    for t in kit["terminology"] + kit["disclaimers"]:
        try:
            re.compile(t.get("pattern") or t.get("trigger"))
        except Exception:
            raise ApiError(400, f"Invalid pattern in rule {t.get('id')}")
    v = ctx.c.execute("SELECT MAX(version)+1 FROM brandkit").fetchone()[0]
    ctx.c.execute("INSERT INTO brandkit(version,json,created_by,ts,note) VALUES(?,?,?,?,?)",
                  (v, json.dumps(kit), ctx.user["id"], now(), str(ctx.body.get("note", ""))[:200]))
    audit(ctx.c, ctx.user, "brandkit_update", None, f"version {v}")
    return 200, {"version": v}


# ------------------------------------------------------------------ stateless check
@route("POST", "/api/check")
def quick_check(ctx):
    kind = ctx.body.get("kind", "text")
    need(kind in ("text", "markdown", "html"), 400, "kind must be text, markdown or html")
    text = str(ctx.body.get("content", ""))
    need(0 < len(text) <= 200_000, 400, "content must be 1 to 200000 characters")
    _, kit = db.latest_kit(ctx.c)
    res = engine.review(kit, kind, text)
    for f in res["findings"]:
        f["status"] = "open"
    return 200, res


# ------------------------------------------------------------------ items
@route("GET", "/api/items")
def list_items(ctx):
    rows = ctx.c.execute("SELECT * FROM items ORDER BY updated DESC").fetchall()
    return 200, {"items": [item_summary(ctx.c, r) for r in rows if can_view(ctx.user, r)]}


@route("POST", "/api/items")
def create_item(ctx):
    b, u, c = ctx.body, ctx.user, ctx.c
    title = str(b.get("title", "")).strip()
    kind = b.get("kind", "text")
    need(title and len(title) <= 150, 400, "Title is required (max 150 characters)")
    need(kind in KINDS, 400, f"kind must be one of {sorted(KINDS)}")
    blob, meta, extra, content = None, {}, [], str(b.get("content", ""))
    if kind in ("docx", "image"):
        try:
            blob = base64.b64decode(b.get("data_b64", ""), validate=True)
        except Exception:
            raise ApiError(400, "data_b64 must be valid base64")
        need(0 < len(blob) <= MAX_IMAGE, 400, "File must be between 1 byte and 4 MB")
        fn = os.path.basename(str(b.get("filename", ""))).strip()
        need(fn, 400, "filename is required")
        if kind == "image":
            need(fn.lower().endswith(IMG_EXT), 400, "Images must be PNG, JPG or SVG")
            meta = {"filename": fn, "alt": str(b.get("alt", ""))[:300]}
        else:
            need(fn.lower().endswith(".docx"), 400, "Documents must be .docx")
            try:
                content, extra = engine.extract_docx(blob)
            except Exception:
                raise ApiError(400, "Could not read this .docx file")
            meta = {"filename": fn}
            blob = None  # original not retained; only extracted text is reviewed
    else:
        need(0 < len(content) <= 200_000, 400, "content must be 1 to 200000 characters")
    c.execute("INSERT INTO items(title,kind,owner_id,status,created,updated,extra_json) VALUES(?,?,?,?,?,?,?)",
              (title, kind, u["id"], "draft", now(), now(), json.dumps(extra)))
    item = get_item(c, c.execute("SELECT last_insert_rowid()").fetchone()[0])
    add_revision(c, item, u, kind, content, "Created", blob, meta)
    audit(c, u, "item_create", item["id"], title)
    return 201, item_detail(c, item, u)


@route("GET", "/api/items/<id>")
def read_item(ctx):
    item = get_item(ctx.c, int(ctx.params["id"]))
    need(can_view(ctx.user, item), 403, "You cannot view this item")
    return 200, item_detail(ctx.c, item, ctx.user)


@route("POST", "/api/items/<id>/revisions")
def new_revision(ctx):
    c, u = ctx.c, ctx.user
    item = get_item(c, int(ctx.params["id"]))
    edit_allowed(u, item)
    kind = item["kind"]
    prev = latest_rev(c, item["id"])
    blob, meta, content = None, {}, str(ctx.body.get("content", ""))
    if kind == "image":
        meta = json.loads(prev["meta_json"])
        blob = prev["blob"]
        if ctx.body.get("data_b64"):
            blob = base64.b64decode(ctx.body["data_b64"])
            need(0 < len(blob) <= MAX_IMAGE, 400, "File must be between 1 byte and 4 MB")
            fn = os.path.basename(str(ctx.body.get("filename", meta["filename"])))
            need(fn.lower().endswith(IMG_EXT), 400, "Images must be PNG, JPG or SVG")
            meta["filename"] = fn
        meta["alt"] = str(ctx.body.get("alt", meta.get("alt", "")))[:300]
        content = ""
    else:
        need(0 < len(content) <= 200_000, 400, "content must be 1 to 200000 characters")
    n = add_revision(c, item, u, kind, content, str(ctx.body.get("note", "Edited"))[:200], blob, meta)
    if item["status"] == "changes_requested":
        c.execute("UPDATE items SET status='draft' WHERE id=?", (item["id"],))
    audit(c, u, "revision", item["id"], f"revision {n}")
    return 201, item_detail(c, get_item(c, item["id"]), u)


@route("GET", "/api/items/<id>/diff")
def diff(ctx):
    c = ctx.c
    item = get_item(c, int(ctx.params["id"]))
    need(can_view(ctx.user, item), 403, "You cannot view this item")
    a, b = int(ctx.query.get("from", 1)), int(ctx.query.get("to", 0))
    ra = c.execute("SELECT * FROM revisions WHERE item_id=? AND n=?", (item["id"], a)).fetchone()
    rb = c.execute("SELECT * FROM revisions WHERE item_id=? AND n=?", (item["id"], b)).fetchone() if b else latest_rev(c, item["id"])
    need(ra and rb, 404, "Revision not found")
    lines = list(difflib.unified_diff(ra["content"].splitlines(), rb["content"].splitlines(),
                                      f"revision {ra['n']}", f"revision {rb['n']}", lineterm=""))
    return 200, {"from": ra["n"], "to": rb["n"], "diff": lines}


@route("POST", "/api/items/<id>/findings/<fid>/accept")
def accept(ctx):
    c, u = ctx.c, ctx.user
    item = get_item(c, int(ctx.params["id"]))
    edit_allowed(u, item)
    need(item["kind"] in ("text", "markdown", "html", "docx"), 400, "Suggestions cannot be applied to images")
    prev = latest_rev(c, item["id"])
    f = next((x for x in json.loads(prev["findings_json"]) if x["fid"] == ctx.params["fid"]), None)
    need(f, 404, "Finding not found in the latest revision")
    try:
        new_text = engine.apply_suggestion(prev["content"], f)
    except ValueError as e:
        raise ApiError(409, str(e))
    n = add_revision(c, item, u, item["kind"], new_text, f"Accepted suggestion: {f['rule_id']}")
    c.execute("INSERT INTO events(item_id,rev_n,key,rule_id,source_id,action,reason,user_id,ts) VALUES(?,?,?,?,?,?,?,?,?)",
              (item["id"], n, f["key"], f["rule_id"], f["source"]["id"], "accepted", "", u["id"], now()))
    audit(c, u, "accept_suggestion", item["id"], f["rule_id"])
    return 200, item_detail(c, get_item(c, item["id"]), u)


@route("POST", "/api/items/<id>/findings/<fid>/dismiss")
def dismiss(ctx):
    c, u = ctx.c, ctx.user
    item = get_item(c, int(ctx.params["id"]))
    need(can_view(u, item), 403, "You cannot view this item")
    reason = str(ctx.body.get("reason", "")).strip()
    need(len(reason) >= 5, 400, "Give a reason (at least 5 characters)")
    prev = latest_rev(c, item["id"])
    f = next((x for x in json.loads(prev["findings_json"]) if x["fid"] == ctx.params["fid"]), None)
    need(f, 404, "Finding not found in the latest revision")
    if f["severity"] == "high":
        need(u["role"] in ROLES_REVIEW and item["owner_id"] != u["id"], 403,
             "High-severity findings can only be dismissed by a reviewer, not the author")
        need(item["status"] == "in_review", 409, "Reviewers dismiss high-severity findings while the item is in review")
    else:
        need(item["owner_id"] == u["id"] or u["role"] in ROLES_REVIEW, 403, "Not allowed")
        need(item["status"] in ("draft", "changes_requested", "in_review"), 409, "Item is locked")
    c.execute("INSERT INTO events(item_id,rev_n,key,rule_id,source_id,action,reason,user_id,ts) VALUES(?,?,?,?,?,?,?,?,?)",
              (item["id"], prev["n"], f["key"], f["rule_id"], f["source"]["id"], "dismissed", reason[:300], u["id"], now()))
    audit(c, u, "dismiss_finding", item["id"], f"{f['rule_id']}: {reason[:100]}")
    return 200, item_detail(c, item, u)


@route("POST", "/api/items/<id>/submit")
def submit(ctx):
    c, u = ctx.c, ctx.user
    item = get_item(c, int(ctx.params["id"]))
    edit_allowed(u, item)
    c.execute("UPDATE items SET status='in_review', updated=? WHERE id=?", (now(), item["id"]))
    audit(c, u, "submit", item["id"])
    return 200, item_detail(c, get_item(c, item["id"]), u)


@route("POST", "/api/items/<id>/decision")
def decision(ctx):
    c, u, b = ctx.c, ctx.user, ctx.body
    item = get_item(c, int(ctx.params["id"]))
    need(u["role"] in ROLES_REVIEW, 403, "Only reviewers, managers and admins can decide")
    need(item["owner_id"] != u["id"], 403, "You cannot review your own work")
    need(item["status"] == "in_review", 409, "Item is not in review")
    rev = latest_rev(c, item["id"])
    d = b.get("decision")
    comment = str(b.get("comment", "")).strip()
    if d == "approve":
        counts = open_counts(annotate(c, item["id"], json.loads(rev["findings_json"])))
        override = str(b.get("override_reason", "")).strip()
        if counts["high"]:
            need(override, 409, f"{counts['high']} high-severity finding(s) are still open. Resolve them, or a manager can approve with an override reason.")
            need(u["role"] in ("manager", "admin"), 403, "Only a manager or admin can override open high-severity findings")
            audit(c, u, "approve_override", item["id"], override)
            c.execute("INSERT INTO events(item_id,rev_n,key,rule_id,source_id,action,reason,user_id,ts) VALUES(?,?,?,?,?,?,?,?,?)",
                      (item["id"], rev["n"], "override", "OVERRIDE", "", "override", override[:300], u["id"], now()))
        c.execute("UPDATE items SET status='approved', updated=? WHERE id=?", (now(), item["id"]))
        audit(c, u, "approve", item["id"])
    elif d == "request_changes":
        need(comment, 400, "A comment explaining the requested changes is required")
        c.execute("UPDATE items SET status='changes_requested', updated=? WHERE id=?", (now(), item["id"]))
        audit(c, u, "request_changes", item["id"])
    else:
        raise ApiError(400, "decision must be approve or request_changes")
    if comment:
        c.execute("INSERT INTO comments(item_id,rev_n,fid,user_id,body,ts) VALUES(?,?,?,?,?,?)",
                  (item["id"], rev["n"], None, u["id"], comment[:2000], now()))
    return 200, item_detail(c, get_item(c, item["id"]), u)


@route("POST", "/api/items/<id>/publish")
def publish(ctx):
    c, u = ctx.c, ctx.user
    item = get_item(c, int(ctx.params["id"]))
    need(u["role"] in ("manager", "admin"), 403, "Only a manager or admin can publish")
    need(item["status"] == "approved", 409, "Only approved items can be published")
    c.execute("UPDATE items SET status='published', updated=? WHERE id=?", (now(), item["id"]))
    audit(c, u, "publish", item["id"])
    return 200, item_detail(c, get_item(c, item["id"]), u)


@route("POST", "/api/items/<id>/comments")
def comment(ctx):
    c, u = ctx.c, ctx.user
    item = get_item(c, int(ctx.params["id"]))
    need(can_view(u, item), 403, "You cannot view this item")
    body = str(ctx.body.get("body", "")).strip()
    need(body and len(body) <= 2000, 400, "Comment must be 1 to 2000 characters")
    rev = latest_rev(c, item["id"])
    c.execute("INSERT INTO comments(item_id,rev_n,fid,user_id,body,ts) VALUES(?,?,?,?,?,?)",
              (item["id"], rev["n"], ctx.body.get("fid"), u["id"], body, now()))
    audit(c, u, "comment", item["id"])
    return 201, item_detail(c, item, u)


@route("GET", "/api/items/<id>/file")
def item_file(ctx):
    item = get_item(ctx.c, int(ctx.params["id"]))
    need(can_view(ctx.user, item), 403, "You cannot view this item")
    need(item["kind"] == "image", 400, "Not an image item")
    r = latest_rev(ctx.c, item["id"])
    fn = json.loads(r["meta_json"])["filename"]
    return 200, ("raw", mimetypes.guess_type(fn)[0] or "application/octet-stream", r["blob"])


@route("GET", "/api/items/<id>/report")
def report(ctx):
    c = ctx.c
    item = get_item(c, int(ctx.params["id"]))
    need(can_view(ctx.user, item), 403, "You cannot view this item")
    d = item_detail(c, item, ctx.user)
    lat = d["latest"]
    L = [f"# Review report: {d['title']}", "", f"- Status: {d['status']}", f"- Owner: {d['owner']}",
         f"- Revision: {lat['n']} (brand kit v{lat['kit_version']})",
         f"- Open findings: high {d['open']['high']}, medium {d['open']['medium']}, low {d['open']['low']}",
         f"- AI disclosure: {'external AI was used for tone suggestions' if lat['ai_used'] else 'No external AI used. Findings come from a rules engine.'}",
         "", "## Findings", ""]
    for f in lat["findings"]:
        L.append(f"### [{f['severity'].upper()}] {f['rule_id']} ({f['status']})")
        L.append(f"- Evidence: \"{f['quote']}\"")
        L.append(f"- Why: {f['message']}")
        L.append(f"- Source: {f['source']['id']} {f['source']['title']}")
        if f["suggestion"]:
            L.append(f"- Suggestion: {f['suggestion']['text']}")
        L.append("")
    L += ["## History", ""] + [f"- Revision {r['n']} by {r['by']}: {r['note']}" for r in d["revisions"]]
    L += ["", "## Comments", ""] + [f"- {x['by']} (rev {x['rev']}): {x['body']}" for x in d["comments"]]
    return 200, ("raw", "text/markdown; charset=utf-8", "\n".join(L).encode())


# ------------------------------------------------------------------ insights & audit
@route("GET", "/api/insights")
def insights(ctx):
    c = ctx.c
    need(ctx.user["role"] in ROLES_REVIEW, 403, "Insights are for reviewers, managers and admins")
    items = c.execute("SELECT i.id,i.status,u.team FROM items i JOIN users u ON u.id=i.owner_id").fetchall()
    by_status = collections.Counter(i["status"] for i in items)
    first = collections.Counter()
    first_cat, by_team, rule_items = collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(set)
    rule_source = {}
    for it in items:
        r = c.execute("SELECT findings_json FROM revisions WHERE item_id=? AND n=1", (it["id"],)).fetchone()
        for f in json.loads(r["findings_json"]):
            first[f["rule_id"]] += 1
            first_cat[f["category"]] += 1
            by_team[it["team"]][f["category"]] += 1
            rule_items[f["rule_id"]].add(it["id"])
            rule_source[f["rule_id"]] = f["source"]["id"]
    ev = collections.defaultdict(lambda: collections.Counter())
    for e in c.execute("SELECT rule_id,action FROM events"):
        ev[e["rule_id"]][e["action"]] += 1
    friction = []
    for rule, cnt in first.most_common():
        acc, dis = ev[rule]["accepted"], ev[rule]["dismissed"]
        decided = acc + dis
        rate = round(dis / decided, 2) if decided else None
        flag = bool(decided >= 3 and rate is not None and rate >= 0.5)
        friction.append({"rule": rule, "guideline": rule_source.get(rule), "found": cnt, "accepted": acc,
                         "dismissed": dis, "dismissal_rate": rate, "items_affected": len(rule_items[rule]),
                         "possibly_unclear": flag})
    recs = []
    for f in friction:
        if f["possibly_unclear"]:
            recs.append(f"Rule {f['rule']} ({f['guideline']}) is dismissed in {int(f['dismissal_rate']*100)}% of decisions. "
                        "Clarify the guideline or add examples; it may be too strict or ambiguous.")
        elif f["items_affected"] >= 2 and f["found"] >= 3:
            recs.append(f"Rule {f['rule']} appears in {f['items_affected']} different items. Consider training or a template.")
    cycles = c.execute("SELECT item_id, COUNT(*) n FROM revisions GROUP BY item_id").fetchall()
    approved_ids = {i["id"] for i in items if i["status"] in ("approved", "published")}
    avg_rev = [x["n"] for x in cycles if x["item_id"] in approved_ids]
    return 200, {"items_total": len(items), "by_status": by_status, "first_pass_by_rule": friction,
                 "first_pass_by_category": first_cat, "by_team": {t: dict(v) for t, v in by_team.items()},
                 "avg_revisions_to_approval": round(sum(avg_rev) / len(avg_rev), 2) if avg_rev else None,
                 "changes_requested_events": c.execute("SELECT COUNT(*) FROM audit WHERE action='request_changes'").fetchone()[0],
                 "overrides": c.execute("SELECT COUNT(*) FROM events WHERE action='override'").fetchone()[0],
                 "recommendations": recs}


@route("GET", "/api/audit")
def audit_log(ctx):
    need(ctx.user["role"] in ("manager", "admin"), 403, "Only managers and admins can read the audit log")
    rows = ctx.c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 200").fetchall()
    return 200, {"audit": [{"ts": r["ts"], "user": user_name(ctx.c, r["user_id"]), "action": r["action"],
                            "item_id": r["item_id"], "detail": r["detail"]} for r in rows]}


# ------------------------------------------------------------------ HTTP plumbing
class Ctx:
    pass


SEC_HEADERS = {
    "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "BrandSentinel/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("BS_QUIET") != "1":
            sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _send(self, status, body, ctype="application/json", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in {**SEC_HEADERS, **(extra or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, default=list).encode())

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path[len("/static/"):] if path.startswith("/static/") else None
        if rel is None:
            return self._json(404, {"error": "Not found"})
        full = os.path.realpath(os.path.join(STATIC, rel))
        if not full.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(full):
            return self._json(404, {"error": "Not found"})
        with open(full, "rb") as f:
            self._send(200, f.read(), mimetypes.guess_type(full)[0] or "application/octet-stream")

    def _dispatch(self, method):
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            return self._static(u.path) if method == "GET" else self._json(405, {"error": "Method not allowed"})
        c = db.connect()
        try:
            for m, rx, fn in ROUTES:
                mt = rx.match(u.path)
                if m == method and mt:
                    ctx = Ctx()
                    ctx.c, ctx.params = c, mt.groupdict()
                    ctx.query = {k: v[0] for k, v in parse_qs(u.query).items()}
                    ctx.body = {}
                    if method in ("POST", "PUT"):
                        n = int(self.headers.get("Content-Length") or 0)
                        if n > MAX_BODY:
                            raise ApiError(413, "Request too large")
                        raw = self.rfile.read(n) if n else b"{}"
                        try:
                            ctx.body = json.loads(raw or b"{}")
                        except ValueError:
                            raise ApiError(400, "Body must be valid JSON")
                        if not isinstance(ctx.body, dict):
                            raise ApiError(400, "Body must be a JSON object")
                    ctx.user = None
                    if not getattr(fn, "public", False):
                        tok = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
                        row = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?",
                                        (tok, now())).fetchone()
                        if not row:
                            raise ApiError(401, "Please log in")
                        ctx.user = row
                    status, out = fn(ctx)
                    c.commit()
                    if isinstance(out, tuple) and out[0] == "raw":
                        extra = {"Content-Security-Policy": "sandbox"} if out[1].startswith("image/svg") else None
                        return self._send(status, out[2], out[1], extra)
                    return self._json(status, out)
            raise ApiError(404, "Not found")
        except ApiError as e:
            c.rollback()
            self._json(e.status, {"error": e.msg})
        except Exception as e:  # never leak internals
            c.rollback()
            sys.stderr.write(f"ERROR {type(e).__name__}: {e}\n")
            self._json(500, {"error": "Something went wrong on the server"})
        finally:
            c.close()

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")


def make_server(host="127.0.0.1", port=8000):
    db.init()
    return ThreadingHTTPServer((host, port), Handler)


def main():
    host = os.environ.get("BS_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("BS_PORT", "8000")))
    srv = make_server(host, port)
    print(f"BrandSentinel running at http://{host}:{port}  (demo users: ana, ben, mira, raj, root / password from BS_DEMO_PASSWORD, default demo123)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
