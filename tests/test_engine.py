import datetime
import io
import json
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import engine  # noqa: E402

KIT = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "brandkit.json")))
TODAY = datetime.date(2026, 10, 21)


def rules(text, kind="text"):
    return {f["rule_id"] for f in engine.review(KIT, kind, text, TODAY)["findings"]}


class Terminology(unittest.TestCase):
    def test_brand_name_case(self):
        self.assertIn("TERM-001", rules("Welcome to LUMORA and lumora."))
        self.assertNotIn("TERM-001", rules("Welcome to Lumora."))

    def test_domain_not_flagged(self):
        self.assertNotIn("TERM-001", rules("Visit lumora.com or mail hello@lumora.com"))

    def test_wrong_product_name_high(self):
        f = engine.review(KIT, "text", "Try Lumora Online today.", TODAY)["findings"]
        self.assertEqual([x["severity"] for x in f if x["rule_id"] == "TERM-002"], ["high"])

    def test_inclusive_language(self):
        self.assertTrue({"TERM-006", "TERM-007"} <= rules("Hey guys, update the blacklist."))


class Claims(unittest.TestCase):
    def test_supported_claim_passes(self):
        r = engine.review(KIT, "text", "More than 2,000 teams use Lumora Cloud.", TODAY)
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["claims"][0]["status"], "supported")

    def test_wrong_number_contradicts(self):
        self.assertIn("CLAIM-MISMATCH", rules("Lumora Cloud delivers 98% uptime."))

    def test_decimal_not_split(self):
        r = engine.review(KIT, "text", "Our uptime is 99.5% this year.", TODAY)
        self.assertEqual(r["claims"][0]["quote"], "Our uptime is 99.5% this year.")

    def test_expired_fact_flagged(self):
        self.assertIn("CLAIM-OUTDATED", rules("Save 20% off annual plans. Terms apply."))
        later = engine.review(KIT, "text", "More than 2,000 teams use Lumora Cloud.", datetime.date(2028, 1, 1))
        self.assertIn("CLAIM-OUTDATED", {f["rule_id"] for f in later["findings"]})

    def test_unverified_statistic(self):
        self.assertIn("CLAIM-UNVERIFIED", rules("Customers grow 300% faster."))

    def test_unsupported_superlative_needs_human(self):
        f = [x for x in engine.review(KIT, "text", "We are guaranteed to be the best.", TODAY)["findings"] if x["rule_id"] == "CLAIM-UNSUPPORTED"]
        self.assertTrue(f and all(x["needs_human"] for x in f))

    def test_offer_needs_terms_line(self):
        self.assertIn("DISC-OFFER", rules("Start your free trial now."))
        self.assertNotIn("DISC-OFFER", rules("Start your free trial now. Terms apply."))


class Voice(unittest.TestCase):
    def test_hype_exclaim_caps(self):
        r = rules("This revolutionary tool is great! Truly great! Try it NOW TODAY.")
        self.assertTrue({"VOICE-HYPE", "VOICE-EXCLAIM", "VOICE-CAPS"} <= r)

    def test_long_sentence(self):
        s = " ".join(["word"] * 40) + "."
        self.assertIn("VOICE-LONG", rules(s))

    def test_clean_text_has_no_findings(self):
        self.assertEqual(rules("Lumora Cloud helps every team plan its work. Plans start at $12 per user per month."), set())


class AccessibilityVisual(unittest.TestCase):
    def test_contrast_math(self):
        self.assertAlmostEqual(engine.contrast_ratio("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertLess(engine.contrast_ratio("#FFFFFF", "#F5A524"), 3)
        self.assertGreater(engine.contrast_ratio("#FFFFFF", "#1F4FD8"), 4.5)

    def test_low_contrast_directive_and_fix(self):
        f = engine.review(KIT, "text", "[colors: fg=#FFFFFF bg=#F5A524]", TODAY)["findings"]
        ax = [x for x in f if x["rule_id"] == "AX-CONTRAST"][0]
        self.assertEqual(ax["suggestion"]["type"], "replace_hex")
        fixed = engine.apply_suggestion("[colors: fg=#FFFFFF bg=#F5A524]", ax)
        self.assertEqual(engine.review(KIT, "text", fixed, TODAY)["findings"], [])

    def test_large_text_threshold(self):
        ok = '<p style="color:#ffffff;background:#1F4FD8">x</p>'
        self.assertNotIn("AX-CONTRAST", rules(ok, "html"))

    def test_html_images(self):
        r = rules('<img src="a.jpg"><img src="logo-old.png" alt="Logo"><img src="logo-primary.svg" width="400" height="200" alt="Lumora logo">', "html")
        self.assertTrue({"AX-ALT-MISSING", "VIS-LOGO-VARIANT", "VIS-LOGO-DISTORTED", "AX-ALT-WEAK"} <= r)

    def test_decorative_empty_alt_allowed(self):
        self.assertNotIn("AX-ALT-MISSING", rules('<img src="a.jpg" alt="">', "html"))

    def test_markdown_image_and_link(self):
        r = rules("![](hero.png) and [click here](/pricing)", "markdown")
        self.assertTrue({"AX-ALT-MISSING", "AX-LINK"} <= r)

    def test_off_palette_color_suggests_nearest(self):
        f = [x for x in engine.review(KIT, "text", "[colors: fg=#1A1A1B bg=#FFFFFF]", TODAY)["findings"] if x["rule_id"] == "VIS-PALETTE"][0]
        self.assertEqual(f["suggestion"]["text"], "#1A1A1A")

    def test_html_visible_text_only(self):
        # long attribute markup must not count as a long sentence
        self.assertNotIn("VOICE-LONG", rules('<a href="' + "x" * 300 + '">Pricing</a>', "html"))


class Suggestions(unittest.TestCase):
    def test_replace_roundtrip_and_stale_guard(self):
        text = "Hey guys, welcome."
        f = [x for x in engine.review(KIT, "text", text, TODAY)["findings"] if x["rule_id"] == "TERM-006"][0]
        self.assertEqual(engine.apply_suggestion(text, f), "Hey everyone, welcome.")
        with self.assertRaises(ValueError):
            engine.apply_suggestion("Hello guys, welcome.", f)

    def test_manual_suggestions_not_applicable(self):
        f = engine.review(KIT, "text", "We are guaranteed to win 300% more.", TODAY)["findings"]
        man = [x for x in f if (x["suggestion"] or {}).get("type") == "manual"][0]
        with self.assertRaises(ValueError):
            engine.apply_suggestion("x", man)

    def test_every_finding_cites_a_source(self):
        txt = "LUMORA is BEST!! Save 20% off annual plans. Customers grow 300% faster. [colors: fg=#fff bg=#F5A524]"
        for f in engine.review(KIT, "text", txt, TODAY)["findings"]:
            self.assertTrue(f["source"]["id"] and f["message"] and f["quote"], f["rule_id"])


class Documents(unittest.TestCase):
    def _docx(self, with_alt):
        buf = io.BytesIO()
        descr = ' descr="A team at a whiteboard"' if with_alt else ""
        xml = ('<w:document xmlns:w="w" xmlns:wp="wp"><w:body><w:p><w:r><w:t>Hello guys &amp; welcome</w:t></w:r></w:p>'
               f'<w:p><w:r><w:drawing><wp:inline><wp:docPr id="1" name="Pic"{descr}/></wp:inline></w:drawing></w:r></w:p></w:body></w:document>')
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", xml)
        return buf.getvalue()

    def test_docx_text_and_missing_alt(self):
        text, extra = engine.extract_docx(self._docx(False))
        self.assertIn("Hello guys & welcome", text)
        self.assertEqual(len(extra), 1)
        self.assertEqual(engine.extract_docx(self._docx(True))[1], [])

    def test_bad_docx_rejected(self):
        with self.assertRaises(Exception):
            engine.extract_docx(b"not a zip")

    def test_png_size_and_logo_distortion(self):
        import struct
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 400, 200) + b"\x08\x06\x00\x00\x00"
        self.assertEqual(engine.image_size(png), (400, 200))
        r = {f["rule_id"] for f in engine.review_image(KIT, "logo-primary.svg", png, "Lumora logo")}
        self.assertIn("VIS-LOGO-DISTORTED", r)
        r2 = {f["rule_id"] for f in engine.review_image(KIT, "photo.png", png, "")}
        self.assertTrue({"AX-ALT-MISSING", "VIS-RESOLUTION"} <= r2)


if __name__ == "__main__":
    unittest.main()
