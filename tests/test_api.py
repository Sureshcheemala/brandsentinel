import base64
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

os.environ["BS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["BS_QUIET"] = "1"
os.environ.pop("BS_EXTERNAL_AI", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import server  # noqa: E402


def call(base, method, path, body=None, token=None, raw=False):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            data = r.read()
            return r.status, (data.decode() if raw else json.loads(data))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


BAD = "LUMORA is the BEST tool ever!! Save 20% off annual plans. Hey guys, e-mail us."


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.tok = {u: call(cls.base, "POST", "/api/login", {"username": u, "password": "demo123"})[1]["token"]
                   for u in ("ana", "ben", "mira", "raj", "root")}

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def c(self, who, method, path, body=None, raw=False):
        return call(self.base, method, path, body, self.tok[who], raw)

    def new_item(self, who="ana", content=BAD, kind="text"):
        s, d = self.c(who, "POST", "/api/items", {"title": "t", "kind": kind, "content": content})
        self.assertEqual(s, 201, d)
        return d

    # ---- auth
    def test_login_required_and_wrong_password(self):
        self.assertEqual(call(self.base, "GET", "/api/items")[0], 401)
        self.assertEqual(call(self.base, "POST", "/api/login", {"username": "ana", "password": "nope"})[0], 401)

    def test_login_throttle(self):
        for _ in range(5):
            call(self.base, "POST", "/api/login", {"username": "ghost", "password": "x"})
        self.assertEqual(call(self.base, "POST", "/api/login", {"username": "ghost", "password": "x"})[0], 429)

    def test_security_headers_and_static(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
            self.assertIn(b"BrandSentinel", r.read())
        self.assertEqual(call(self.base, "GET", "/static/../db.py")[0], 404)

    # ---- review
    def test_create_runs_review_with_sources(self):
        d = self.new_item()
        rules = {f["rule_id"] for f in d["latest"]["findings"]}
        self.assertTrue({"TERM-001", "CLAIM-UNSUPPORTED", "CLAIM-OUTDATED", "TERM-006"} <= rules)
        self.assertTrue(all(f["source"]["id"] for f in d["latest"]["findings"]))
        self.assertEqual(d["status"], "draft")

    def test_quick_check_is_stateless(self):
        before = len(self.c("ana", "GET", "/api/items")[1]["items"])
        s, r = self.c("ana", "POST", "/api/check", {"content": BAD})
        self.assertEqual(s, 200)
        self.assertTrue(r["findings"])
        self.assertEqual(len(self.c("ana", "GET", "/api/items")[1]["items"]), before)

    def test_validation(self):
        self.assertEqual(self.c("ana", "POST", "/api/items", {"title": "", "content": "x"})[0], 400)
        self.assertEqual(self.c("ana", "POST", "/api/items", {"title": "t", "kind": "exe", "content": "x"})[0], 400)
        self.assertEqual(self.c("ana", "POST", "/api/items", {"title": "t", "kind": "image", "filename": "a.exe", "data_b64": "AAAA"})[0], 400)
        self.assertEqual(self.c("ana", "POST", "/api/items", {"title": "t", "kind": "docx", "filename": "a.docx", "data_b64": base64.b64encode(b"junk").decode()})[0], 400)

    # ---- suggestions are human-triggered
    def test_accept_creates_revision_and_resolves(self):
        d = self.new_item(content="Hey guys, welcome to Lumora.")
        f = next(x for x in d["latest"]["findings"] if x["rule_id"] == "TERM-006")
        s, d2 = self.c("ana", "POST", f"/api/items/{d['id']}/findings/{f['fid']}/accept")
        self.assertEqual(s, 200, d2)
        self.assertEqual(d2["latest"]["content"], "Hey everyone, welcome to Lumora.")
        self.assertEqual(d2["latest"]["n"], 2)
        self.assertEqual(d2["open"], {"high": 0, "medium": 0, "low": 0})
        s, df = self.c("ana", "GET", f"/api/items/{d['id']}/diff?from=1&to=2")
        self.assertTrue(any(l.startswith("+Hey everyone") for l in df["diff"]))

    def test_manual_suggestion_cannot_be_accepted(self):
        d = self.new_item(content="We are guaranteed to grow 300% faster.")
        f = next(x for x in d["latest"]["findings"] if x["rule_id"] == "CLAIM-UNVERIFIED")
        self.assertEqual(self.c("ana", "POST", f"/api/items/{d['id']}/findings/{f['fid']}/accept")[0], 409)

    def test_dismiss_needs_reason_and_persists_across_revisions(self):
        d = self.new_item(content="Please utilize the new board.")
        f = d["latest"]["findings"][0]
        self.assertEqual(self.c("ana", "POST", f"/api/items/{d['id']}/findings/{f['fid']}/dismiss", {"reason": ""})[0], 400)
        s, d2 = self.c("ana", "POST", f"/api/items/{d['id']}/findings/{f['fid']}/dismiss", {"reason": "Quoted from customer"})
        self.assertEqual(s, 200)
        s, d3 = self.c("ana", "POST", f"/api/items/{d['id']}/revisions", {"content": "Please utilize the new board today."})
        self.assertEqual(d3["open"]["low"], 0)

    # ---- roles and workflow
    def test_creator_cannot_dismiss_high_or_review(self):
        d = self.new_item(content="Try Lumora Online today.")
        f = next(x for x in d["latest"]["findings"] if x["severity"] == "high")
        s, r = self.c("ana", "POST", f"/api/items/{d['id']}/findings/{f['fid']}/dismiss", {"reason": "I disagree strongly"})
        self.assertEqual(s, 403)
        self.c("ana", "POST", f"/api/items/{d['id']}/submit")
        self.assertEqual(self.c("ana", "POST", f"/api/items/{d['id']}/decision", {"decision": "approve"})[0], 403)

    def test_privacy_between_creators_and_drafts(self):
        d = self.new_item("ana")
        self.assertEqual(self.c("ben", "GET", f"/api/items/{d['id']}")[0], 403)
        self.assertEqual(self.c("mira", "GET", f"/api/items/{d['id']}")[0], 403)  # reviewers don't see drafts
        self.assertEqual(self.c("raj", "GET", f"/api/items/{d['id']}")[0], 200)

    def test_full_workflow_with_high_block_and_override(self):
        d = self.new_item(content="Try Lumora Online today.")
        i = d["id"]
        self.assertEqual(self.c("ana", "POST", f"/api/items/{i}/submit")[0], 200)
        self.assertEqual(self.c("ana", "POST", f"/api/items/{i}/revisions", {"content": "x"})[0], 409)  # locked
        s, r = self.c("mira", "POST", f"/api/items/{i}/decision", {"decision": "approve"})
        self.assertEqual(s, 409)  # open high finding blocks approval
        s, r = self.c("mira", "POST", f"/api/items/{i}/decision", {"decision": "request_changes"})
        self.assertEqual(s, 400)  # comment required
        s, r = self.c("mira", "POST", f"/api/items/{i}/decision", {"decision": "request_changes", "comment": "Use the product name"})
        self.assertEqual(r["status"], "changes_requested")
        s, r = self.c("ana", "POST", f"/api/items/{i}/revisions", {"content": "Try Lumora Cloud today."})
        self.assertEqual(r["status"], "draft")
        self.c("ana", "POST", f"/api/items/{i}/submit")
        s, r = self.c("mira", "POST", f"/api/items/{i}/decision", {"decision": "approve", "comment": "Looks good"})
        self.assertEqual(r["status"], "approved")
        self.assertEqual(self.c("mira", "POST", f"/api/items/{i}/publish")[0], 403)
        s, r = self.c("raj", "POST", f"/api/items/{i}/publish")
        self.assertEqual(r["status"], "published")
        s, rep = self.c("ana", "GET", f"/api/items/{i}/report", raw=True)
        self.assertIn("No external AI used", rep)

    def test_override_only_for_managers_and_is_audited(self):
        d = self.new_item(content="Try Lumora Online today.")
        i = d["id"]
        self.c("ana", "POST", f"/api/items/{i}/submit")
        s, r = self.c("mira", "POST", f"/api/items/{i}/decision", {"decision": "approve", "override_reason": "Legal cleared it"})
        self.assertEqual(s, 403)
        s, r = self.c("raj", "POST", f"/api/items/{i}/decision", {"decision": "approve", "override_reason": "Legal cleared it"})
        self.assertEqual(r["status"], "approved")
        aud = self.c("raj", "GET", "/api/audit")[1]["audit"]
        self.assertTrue(any(a["action"] == "approve_override" for a in aud))
        self.assertEqual(self.c("ana", "GET", "/api/audit")[0], 403)

    def test_comments(self):
        d = self.new_item()
        s, r = self.c("ana", "POST", f"/api/items/{d['id']}/comments", {"body": "Question about the claim"})
        self.assertEqual(r["comments"][0]["body"], "Question about the claim")
        self.assertEqual(self.c("ana", "POST", f"/api/items/{d['id']}/comments", {"body": ""})[0], 400)

    # ---- file types
    def test_docx_and_image_flow(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="w" xmlns:wp="wp"><w:body><w:p><w:r><w:t>Hey guys</w:t></w:r></w:p><wp:docPr id="1" name="p"/></w:body></w:document>')
        s, d = self.c("ana", "POST", "/api/items", {"title": "doc", "kind": "docx", "filename": "a.docx", "data_b64": base64.b64encode(buf.getvalue()).decode()})
        self.assertEqual(s, 201, d)
        self.assertTrue({"TERM-006", "AX-ALT-MISSING"} <= {f["rule_id"] for f in d["latest"]["findings"]})
        png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x90\x00\x00\x00\xc8\x08\x06\x00\x00\x00"
        s, d = self.c("ana", "POST", "/api/items", {"title": "img", "kind": "image", "filename": "photo.png", "alt": "", "data_b64": base64.b64encode(png).decode()})
        self.assertEqual(s, 201, d)
        self.assertIn("AX-ALT-MISSING", {f["rule_id"] for f in d["latest"]["findings"]})
        s, d2 = self.c("ana", "POST", f"/api/items/{d['id']}/revisions", {"alt": "Team planning on a board"})
        self.assertNotIn("AX-ALT-MISSING", {f["rule_id"] for f in d2["latest"]["findings"]})

    # ---- insights and brand kit
    def test_insights_roles_and_content(self):
        self.new_item(content="Hey guys.")
        self.assertEqual(self.c("ana", "GET", "/api/insights")[0], 403)
        s, r = self.c("mira", "GET", "/api/insights")
        self.assertEqual(s, 200)
        self.assertTrue(r["first_pass_by_rule"])

    def test_brandkit_admin_only_and_versioned(self):
        s, d = self.c("ana", "GET", "/api/brandkit")
        kit = d["kit"]
        self.assertEqual(self.c("ana", "PUT", "/api/brandkit", {"kit": kit})[0], 403)
        kit["terminology"].append({"id": "TERM-X", "pattern": "(", "message": "bad", "guideline": "G-LANG", "use": "x"})
        self.assertEqual(self.c("root", "PUT", "/api/brandkit", {"kit": kit})[0], 400)  # invalid regex rejected
        kit["terminology"].pop()
        s, r = self.c("root", "PUT", "/api/brandkit", {"kit": kit, "note": "test"})
        self.assertEqual(s, 200)
        self.assertGreater(r["version"], 1)

    def test_ai_disclosure_defaults_off(self):
        s, d = call(self.base, "GET", "/api/disclosure")
        self.assertFalse(d["ai"]["enabled"])
        self.assertEqual(d["external_services"], [])

    def test_xss_text_is_stored_verbatim_and_json_escaped(self):
        d = self.new_item(content="<script>alert(1)</script> Hey guys")
        self.assertIn("<script>", d["latest"]["content"])  # UI renders with textContent; API returns data only


    def test_health_endpoint_is_public(self):
        code, body = call(self.base, "GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])


if __name__ == "__main__":
    unittest.main()
