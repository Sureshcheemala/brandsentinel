"""Populate a running BrandSentinel server with realistic demo activity (for the insights page).

Usage:  python3 run.py &   then   python3 seed_demo.py [http://127.0.0.1:8000]
"""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def call(method, path, body=None, tok=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + tok} if tok else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read()).get("error"), "status": e.code}


tok = {u: call("POST", "/api/login", {"username": u, "password": "demo123"})["token"] for u in ("ana", "ben", "mira", "raj")}
drafts = [
    ("ana", "Autumn launch email", "LUMORA is the BEST project tool ever!! Our revolutionary platform delivers 99.5% uptime. Get a free trial today and save 20% off annual plans.\nHey guys, e-mail us anytime."),
    ("ana", "Webinar invite", "JOIN OUR WEBINAR TODAY! Learn how to leverage synergy across teams. Customers grow 300% faster. Hey guys, bring a friend!"),
    ("ben", "Regional promo", "Lumora Online is the fastest and best tool. It is guaranteed to cut costs. Hey guys, e-mail the whitelist to us."),
    ("ben", "Pricing page note", "Plans start at $9 per user per month. Try Lumora Cloud free for 14 days. Terms apply."),
    ("ana", "Customer story", "More than 2,000 teams use Lumora Cloud. Lumora Cloud helps every team plan its work with confidence."),
    ("ben", "Social post", "Cheap, fast and revolutionary! Utilize Lumora today. Hey guys, check it out!"),
]
ids = []
for who, title, text in drafts:
    d = call("POST", "/api/items", {"title": title, "kind": "text", "content": text}, tok[who])
    ids.append((who, d["id"], d))
# a creator accepts every auto-applicable low/medium fix on the first two items, dismisses claim-style findings with reasons
for who, i, d in ids[:3]:
    for f in d["latest"]["findings"]:
        if f["suggestion"] and f["suggestion"]["type"] in ("replace",) and f["severity"] != "high" and f["rule_id"].startswith(("TERM", "VOICE")):
            cur = call("GET", f"/api/items/{i}", tok=tok[who])
            g = next((x for x in cur["latest"]["findings"] if x["rule_id"] == f["rule_id"] and x["quote"] == f["quote"] and x["status"] == "open"), None)
            if g:
                call("POST", f"/api/items/{i}/findings/{g['fid']}/accept", tok=tok[who])
for who, i, d in ids[1:4]:
    cur = call("GET", f"/api/items/{i}", tok=tok[who])
    for f in cur["latest"]["findings"]:
        if f["rule_id"] == "VOICE-CAPS" or f["rule_id"] == "CLAIM-UNSUPPORTED" and f["severity"] == "medium":
            call("POST", f"/api/items/{i}/findings/{f['fid']}/dismiss", {"reason": "Intentional emphasis for this campaign"}, tok[who])
# submit and review
for who, i, d in ids[:2] + ids[3:5]:
    call("POST", f"/api/items/{i}/submit", tok=tok[who])
call("POST", f"/api/items/{ids[0][1]}/decision", {"decision": "request_changes", "comment": "Fix the uptime figure and remove the expired promo."}, tok["mira"])
call("POST", f"/api/items/{ids[3][1]}/decision", {"decision": "request_changes", "comment": "Price must match the pricing page ($12)."}, tok["mira"])
call("POST", f"/api/items/{ids[4][1]}/decision", {"decision": "approve", "comment": "Good to go."}, tok["mira"])
call("POST", f"/api/items/{ids[4][1]}/publish", tok=tok["raj"])
print("Seeded", len(ids), "items. Log in as mira (reviewer) or raj (manager) and open Insights.")
