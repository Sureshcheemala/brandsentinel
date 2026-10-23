"use strict";
// BrandSentinel single-page UI. All user content is rendered with textContent (never innerHTML).
const S = {token: sessionStorage.getItem("bs_token"), user: JSON.parse(sessionStorage.getItem("bs_user") || "null")};
const $ = (s) => document.querySelector(s);
const SAMPLES = {
  "Launch email (many issues)": {kind: "text", title: "Autumn launch email", content:
    "LUMORA is the BEST project tool ever!! Our revolutionary platform delivers 99.5% uptime and we are guaranteed to be the fastest.\nGet a free trial today and save 20% off annual plans. Join more than 2,000 teams who use Lumora Cloud.\nHey guys, grow your output 300% faster and e-mail us anytime.\n[colors: fg=#FFFFFF bg=#F5A524]"},
  "Clean post (should pass)": {kind: "text", title: "Product update", content:
    "Lumora Cloud now supports shared boards for every team. More than 2,000 teams use Lumora Cloud today.\nPlans start at $12 per user per month. Try Lumora Cloud free for 14 days. Terms apply."},
  "Landing page HTML": {kind: "html", title: "Pricing banner", content:
    "<div style=\"color:#ffffff;background:#F5A524\"><h2>Lumora Online pricing</h2><img src=\"logo-old.png\" width=\"400\" height=\"200\"><img src=\"hero.jpg\"><a href=\"/pricing\">click here</a></div>"},
};

async function api(path, opts = {}) {
  const r = await fetch(path, {method: opts.method || "GET", headers: {"Content-Type": "application/json",
    ...(S.token ? {Authorization: "Bearer " + S.token} : {})}, body: opts.body ? JSON.stringify(opts.body) : undefined});
  const type = r.headers.get("content-type") || "";
  const data = type.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    if (r.status === 401 && S.token) { logout(); }
    throw new Error((data && data.error) || "Request failed");
  }
  return data;
}
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, "");
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return e;
}
function toast(msg, ok) {
  const t = $("#toast"); t.textContent = msg; t.className = ok ? "ok" : ""; t.style.display = "block";
  $("#live").textContent = msg; setTimeout(() => (t.style.display = "none"), 4500);
}
const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message); } };
const badge = (text, cls) => h("span", {class: "badge " + cls}, text);
const sev = (s) => badge(s, "b-" + s);
const fmt = (ts) => new Date(ts * 1000).toLocaleString();

function logout() { S.token = null; S.user = null; sessionStorage.clear(); render(); }
function go(hash) { location.hash = hash; }

const NAV = [["items", "Content"], ["new", "New review"], ["check", "Quick check"], ["insights", "Insights"],
  ["kit", "Brand kit"], ["audit", "Audit log"], ["disclosure", "AI & data"]];
function renderNav(cur) {
  const nav = $("#nav"); nav.replaceChildren();
  if (!S.user) return;
  for (const [id, label] of NAV) {
    if (id === "insights" && S.user.role === "creator") continue;
    if (id === "audit" && !["manager", "admin"].includes(S.user.role)) continue;
    nav.append(h("button", {"aria-current": cur === id ? "page" : null, onclick: () => go(id)}, label));
  }
  $("#who").replaceChildren(h("span", {}, `${S.user.name} (${S.user.role}) `), h("button", {class: "btn secondary", onclick: logout}, "Log out"));
}

// ---------------------------------------------------------------- views
function viewLogin() {
  const u = h("input", {id: "u", autocomplete: "username", value: "ana"}), p = h("input", {id: "p", type: "password", autocomplete: "current-password"});
  const f = h("form", {class: "card", onsubmit: guard(async (e) => {
    e.preventDefault();
    const r = await api("/api/login", {method: "POST", body: {username: u.value, password: p.value}});
    S.token = r.token; S.user = r.user; sessionStorage.setItem("bs_token", r.token); sessionStorage.setItem("bs_user", JSON.stringify(r.user)); go("items"); render();
  })}, h("h2", {}, "Sign in"), h("label", {for: "u"}, "Username"), u, h("label", {for: "p"}, "Password"), p,
    h("p", {}, h("button", {class: "btn"}, "Sign in")),
    h("h3", {}, "Try it in one click (demo accounts)"),
    h("div", {class: "row"}, [["Ana (creator)", "ana"], ["Mira (reviewer)", "mira"], ["Raj (manager)", "raj"], ["Root (admin)", "root"]].map(([label, name]) =>
      h("button", {type: "button", class: "btn secondary", onclick: () => { u.value = name; p.value = "demo123"; f.requestSubmit(); }}, label))),
    h("p", {class: "muted"}, "Demo users: ana and ben (creators), mira (reviewer), raj (manager), root (admin). Default password: demo123."));
  return f;
}

async function viewItems() {
  const {items} = await api("/api/items");
  const rows = items.map((i) => h("tr", {}, h("td", {}, h("a", {href: "#item/" + i.id}, i.title)), h("td", {}, i.kind), h("td", {}, badge(i.status.replace("_", " "), "b-status")),
    h("td", {}, i.owner), h("td", {}, i.open.high ? sev("high") : null, i.open.high ? ` ${i.open.high} ` : "", i.open.medium ? sev("medium") : null, i.open.medium ? ` ${i.open.medium} ` : "", i.open.low ? sev("low") : null, i.open.low ? ` ${i.open.low}` : "", (!i.open.high && !i.open.medium && !i.open.low) ? badge("no open findings", "b-ok") : null),
    h("td", {}, "r" + i.revision), h("td", {}, fmt(i.updated))));
  return h("div", {}, h("div", {class: "row"}, h("h2", {}, "Content"), h("button", {class: "btn", onclick: () => go("new")}, "New review")),
    h("div", {class: "card"}, items.length ? h("table", {}, h("thead", {}, h("tr", {}, ["Title", "Type", "Status", "Owner", "Open findings", "Rev", "Updated"].map((x) => h("th", {}, x)))), h("tbody", {}, rows)) : h("p", {}, "Nothing here yet. Create a new review.")));
}

function viewNew() {
  const title = h("input", {id: "t", maxlength: 150}), kind = h("select", {id: "k"}, ["text", "markdown", "html", "docx", "image"].map((k) => h("option", {value: k}, k)));
  const ta = h("textarea", {id: "c"}), file = h("input", {id: "f", type: "file"}), alt = h("input", {id: "a", maxlength: 300});
  const sample = h("select", {id: "s", "aria-label": "Load a sample"}, h("option", {value: ""}, "Load a sample draft…"), Object.keys(SAMPLES).map((k) => h("option", {value: k}, k)));
  sample.onchange = () => { const s = SAMPLES[sample.value]; if (s) { title.value = s.title; kind.value = s.kind; ta.value = s.content; sync(); } };
  const fileBox = h("div", {}, h("label", {for: "f"}, "File (.docx or PNG/JPG/SVG, max 4 MB)"), file, h("label", {for: "a"}, "Alt text (images)"), alt);
  const textBox = h("div", {}, h("label", {for: "c"}, "Content"), ta, h("p", {class: "muted"}, "Tip: add a line like [colors: fg=#ffffff bg=#1f4fd8] to check a text/background pair in plain text."));
  function sync() { const f = ["docx", "image"].includes(kind.value); fileBox.hidden = !f; textBox.hidden = f; }
  kind.onchange = sync;
  const form = h("form", {class: "card", onsubmit: guard(async (e) => {
    e.preventDefault();
    const body = {title: title.value, kind: kind.value};
    if (["docx", "image"].includes(kind.value)) {
      const fl = file.files[0]; if (!fl) throw new Error("Choose a file");
      body.filename = fl.name; body.alt = alt.value;
      body.data_b64 = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.onerror = rej; r.readAsDataURL(fl); });
    } else body.content = ta.value;
    const d = await api("/api/items", {method: "POST", body});
    toast("Review complete", true); go("item/" + d.id);
  })}, h("h2", {}, "New review"), sample, h("label", {for: "t"}, "Title"), title, h("label", {for: "k"}, "Content type"), kind, textBox, fileBox, h("p", {}, h("button", {class: "btn"}, "Create and review")));
  sync(); return form;
}

function viewCheck() {
  const ta = h("textarea", {id: "q"}), kind = h("select", {id: "qk"}, ["text", "markdown", "html"].map((k) => h("option", {value: k}, k)));
  const out = h("div", {});
  ta.value = SAMPLES["Launch email (many issues)"].content;
  const btn = h("button", {class: "btn", onclick: guard(async () => {
    const r = await api("/api/check", {method: "POST", body: {content: ta.value, kind: kind.value}});
    out.replaceChildren(h("h3", {}, `${r.findings.length} finding(s). Nothing was saved.`), ...r.findings.map((f) => findingCard(f, null)));
  })}, "Check now");
  return h("div", {}, h("h2", {}, "Quick check"), h("p", {class: "muted"}, "Stateless dry run. Nothing is stored and no workflow starts."), h("label", {for: "qk"}, "Type"), kind, h("label", {for: "q"}, "Draft"), ta, h("p", {}, btn), out);
}

function findingCard(f, ctx) {
  const c = h("div", {class: `finding ${f.severity} ${f.status === "dismissed" ? "dismissed" : ""}`, id: "f-" + f.fid},
    h("div", {class: "row"}, sev(f.severity), badge(f.category, "b-status"), h("strong", {}, f.rule_id), f.status === "dismissed" ? badge("dismissed", "b-ok") : null,
      f.needs_human ? badge("needs human judgement", "b-medium") : null, f.ai_assisted ? badge("AI-assisted", "b-low") : null),
    h("p", {}, h("em", {}, "“" + f.quote + "”")), h("p", {}, f.message),
    h("div", {class: "src"}, h("strong", {}, `Source ${f.source.id}: ${f.source.title}`), h("br"), f.source.excerpt),
    f.suggestion ? h("p", {}, h("strong", {}, "Suggestion: "), f.suggestion.type === "replace" ? `replace with “${f.suggestion.text}”` : f.suggestion.type === "replace_hex" ? `change ${f.suggestion.target} to ${f.suggestion.text}` : f.suggestion.text) : null,
    f.status === "dismissed" ? h("p", {class: "muted"}, `Dismissed by ${f.dismissed_by}: ${f.dismiss_reason}`) : null);
  if (ctx && f.status === "open") {
    const row = h("div", {class: "row"});
    if (ctx.can_edit && f.suggestion && ["replace", "replace_hex", "append"].includes(f.suggestion.type))
      row.append(h("button", {class: "btn", onclick: guard(async () => { await api(`/api/items/${ctx.id}/findings/${encodeURIComponent(f.fid)}/accept`, {method: "POST"}); toast("Suggestion applied as a new revision", true); render(); })}, "Accept suggestion"));
    row.append(h("button", {class: "btn secondary", onclick: guard(async () => {
      const reason = prompt("Why is this finding not a problem? (a reason is recorded)"); if (!reason) return;
      await api(`/api/items/${ctx.id}/findings/${encodeURIComponent(f.fid)}/dismiss`, {method: "POST", body: {reason}}); toast("Dismissed with reason", true); render();
    })}, "Dismiss with reason"));
    c.append(row);
  }
  return c;
}

function highlighted(content, findings) {
  const segs = findings.filter((f) => f.start >= 0).sort((a, b) => a.start - b.start);
  const box = h("div", {class: "doc", tabindex: 0, "aria-label": "Content with highlighted findings"});
  let pos = 0;
  for (const f of segs) {
    if (f.start < pos) continue;
    box.append(content.slice(pos, f.start));
    const m = h("mark", {class: "s-" + (f.status === "dismissed" ? "dismissed" : f.severity), title: f.rule_id + ": " + f.message, onclick: () => { const el = document.getElementById("f-" + f.fid); if (el) { el.scrollIntoView({behavior: "smooth", block: "center"}); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1500); } }}, content.slice(f.start, f.end));
    box.append(m); pos = f.end;
  }
  box.append(content.slice(pos)); return box;
}

async function viewItem(id) {
  const d = await api("/api/items/" + id);
  const L = d.latest, u = S.user, isOwner = d.owner_id === u.id, canReview = ["reviewer", "manager", "admin"].includes(u.role) && !isOwner;
  const left = h("div", {});
  left.append(h("div", {class: "card"}, h("div", {class: "row"}, h("h2", {}, d.title), badge(d.status.replace("_", " "), "b-status"), badge(d.kind, "b-status"), h("span", {class: "muted"}, `rev ${L.n} · brand kit v${L.kit_version} · by ${L.by}`)),
    L.ai_used ? h("p", {class: "muted"}, "External AI contributed tone suggestions on this revision. They are labelled and need human judgement.") : h("p", {class: "muted"}, "No external AI used. Findings come from the rules engine."),
    d.kind === "image" ? h("div", {}, h("p", {}, `File: ${L.meta.filename} · alt text: ${L.meta.alt || "(none)"}`)) : highlighted(L.content, L.findings)));
  if (d.can_edit) {
    if (d.kind === "image") {
      const alt = h("input", {id: "ealt", value: L.meta.alt || ""}), file = h("input", {type: "file", id: "efile", "aria-label": "Replace image"});
      left.append(h("div", {class: "card"}, h("h3", {}, "Edit"), h("label", {for: "ealt"}, "Alt text"), alt, h("label", {for: "efile"}, "Replace image (optional)"), file,
        h("p", {}, h("button", {class: "btn", onclick: guard(async () => {
          const body = {alt: alt.value, note: "Updated image details"};
          if (file.files[0]) { body.filename = file.files[0].name; body.data_b64 = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.readAsDataURL(file.files[0]); }); }
          await api(`/api/items/${id}/revisions`, {method: "POST", body}); toast("New revision saved", true); render();
        })}, "Save and re-check"))));
    } else {
      const ta = h("textarea", {id: "edit"}); ta.value = L.content;
      left.append(h("div", {class: "card"}, h("h3", {}, "Edit"), h("label", {for: "edit"}, "Content (saving creates a new revision and re-checks)"), ta,
        h("p", {}, h("button", {class: "btn", onclick: guard(async () => { await api(`/api/items/${id}/revisions`, {method: "POST", body: {content: ta.value, note: "Manual edit"}}); toast("New revision saved", true); render(); })}, "Save and re-check"))));
    }
  }
  // workflow
  const wf = h("div", {class: "card"}, h("h3", {}, "Workflow"));
  if (d.can_edit) wf.append(h("button", {class: "btn", onclick: guard(async () => { await api(`/api/items/${id}/submit`, {method: "POST"}); toast("Submitted for review", true); render(); })}, "Submit for review"));
  if (canReview && d.status === "in_review") {
    const cm = h("textarea", {id: "cm", "aria-label": "Decision comment"}); cm.className = "small"; cm.style.minHeight = "70px";
    const ov = h("input", {id: "ov", placeholder: "Override reason (managers only, if high findings are open)"});
    wf.append(h("label", {for: "cm"}, "Comment"), cm, ov, h("div", {class: "row"},
      h("button", {class: "btn", onclick: guard(async () => { await api(`/api/items/${id}/decision`, {method: "POST", body: {decision: "approve", comment: cm.value, override_reason: ov.value}}); toast("Approved", true); render(); })}, "Approve"),
      h("button", {class: "btn danger", onclick: guard(async () => { await api(`/api/items/${id}/decision`, {method: "POST", body: {decision: "request_changes", comment: cm.value}}); toast("Changes requested", true); render(); })}, "Request changes")));
  }
  if (["manager", "admin"].includes(u.role) && d.status === "approved") wf.append(h("button", {class: "btn", onclick: guard(async () => { await api(`/api/items/${id}/publish`, {method: "POST"}); toast("Published", true); render(); })}, "Publish"));
  if (d.status === "published") wf.append(h("p", {}, "Published. Locked."));
  wf.append(h("p", {}, h("a", {href: `/api/items/${id}/report`, onclick: guard(async (e) => { e.preventDefault(); const t = await api(`/api/items/${id}/report`); const a = h("a", {href: URL.createObjectURL(new Blob([t], {type: "text/markdown"})), download: `review-${id}.md`}); document.body.append(a); a.click(); a.remove(); })}, "Download review report (.md)")));
  left.append(wf);
  // comments
  const cin = h("input", {id: "newc", "aria-label": "Add a comment", maxlength: 2000});
  left.append(h("div", {class: "card"}, h("h3", {}, "Comments"), d.comments.length ? d.comments.map((c) => h("p", {}, h("strong", {}, c.by), ` (rev ${c.rev}, ${fmt(c.ts)}): ${c.body}`)) : h("p", {class: "muted"}, "No comments yet."),
    h("div", {class: "row"}, cin, h("button", {class: "btn secondary", onclick: guard(async () => { if (!cin.value.trim()) return; await api(`/api/items/${id}/comments`, {method: "POST", body: {body: cin.value}}); render(); })}, "Comment"))));
  // history
  const diffOut = h("pre", {class: "diff", hidden: true});
  left.append(h("div", {class: "card"}, h("h3", {}, "Revision history"), h("table", {}, h("tbody", {}, d.revisions.map((r) => h("tr", {}, h("td", {}, "r" + r.n), h("td", {}, r.note), h("td", {}, r.by), h("td", {}, fmt(r.ts)),
    h("td", {}, d.kind !== "image" && r.n > 1 ? h("button", {class: "btn secondary", onclick: guard(async () => { const x = await api(`/api/items/${id}/diff?from=${r.n - 1}&to=${r.n}`); diffOut.hidden = false; diffOut.replaceChildren(...x.diff.map((ln) => h("div", {class: ln.startsWith("+") && !ln.startsWith("+++") ? "ins" : ln.startsWith("-") && !ln.startsWith("---") ? "del" : ""}, ln || " "))); })}, "Show changes") : null))))), diffOut,
    d.events.length ? h("div", {}, h("h4", {}, "Decisions on findings"), d.events.map((e) => h("p", {class: "muted"}, `r${e.rev} ${e.by}: ${e.action} ${e.rule}${e.reason ? " – " + e.reason : ""}`))) : null));
  // right column: findings
  const open = L.findings.filter((f) => f.status === "open"), done = L.findings.filter((f) => f.status !== "open");
  const right = h("div", {}, h("div", {class: "card"}, h("h3", {}, `Findings (${open.length} open)`), h("p", {class: "muted"}, "Suggestions are never applied automatically."),
    open.length ? open.map((f) => findingCard(f, d)) : h("p", {}, badge("No open findings", "b-ok")),
    done.length ? h("details", {}, h("summary", {}, `${done.length} dismissed`), done.map((f) => findingCard(f, d))) : null));
  if (L.claims.length) right.append(h("div", {class: "card"}, h("h3", {}, "Claims checked"), h("table", {}, h("tbody", {}, L.claims.map((c) => h("tr", {}, h("td", {}, c.quote), h("td", {}, badge(c.status, c.status === "supported" ? "b-ok" : "b-medium")), h("td", {}, c.fact_id || "no approved fact")))))));
  return h("div", {class: "grid"}, left, right);
}

async function viewInsights() {
  const d = await api("/api/insights");
  const t = (head, rows) => h("table", {}, h("thead", {}, h("tr", {}, head.map((x) => h("th", {}, x)))), h("tbody", {}, rows));
  return h("div", {}, h("h2", {}, "Governance insights"),
    h("div", {class: "card"}, h("h3", {}, "Recommendations"), d.recommendations.length ? h("ul", {}, d.recommendations.map((r) => h("li", {}, r))) : h("p", {class: "muted"}, "Not enough decisions yet. Dismissal patterns appear after reviews.")),
    h("div", {class: "card"}, h("h3", {}, "Repeated mistakes and guideline clarity (first drafts)"), t(["Rule", "Guideline", "Found", "Items", "Accepted", "Dismissed", "Dismissal rate", "Signal"], d.first_pass_by_rule.map((r) => h("tr", {}, h("td", {}, r.rule), h("td", {}, r.guideline), h("td", {}, r.found), h("td", {}, r.items_affected), h("td", {}, r.accepted), h("td", {}, r.dismissed), h("td", {}, r.dismissal_rate == null ? "n/a" : Math.round(r.dismissal_rate * 100) + "%"), h("td", {}, r.possibly_unclear ? badge("possibly unclear", "b-medium") : ""))))),
    h("div", {class: "card"}, h("h3", {}, "Overview"), h("p", {}, `Items: ${d.items_total}. Average revisions to approval: ${d.avg_revisions_to_approval ?? "n/a"}. Changes requested: ${d.changes_requested_events}. Overrides of high findings: ${d.overrides}.`),
      t(["Status", "Count"], Object.entries(d.by_status).map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", {}, v)))),
      t(["Team", "Findings by category (first drafts)"], Object.entries(d.by_team).map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", {}, Object.entries(v).map(([a, b]) => `${a}: ${b}`).join(", ")))))));
}

async function viewKit() {
  const d = await api("/api/brandkit"), k = d.kit;
  const root = h("div", {}, h("h2", {}, `Brand kit v${d.version} — ${k.brand}`), h("p", {class: "muted"}, k.note),
    h("div", {class: "card"}, h("h3", {}, "Guidelines"), h("table", {}, h("tbody", {}, k.guidelines.map((g) => h("tr", {}, h("td", {}, h("strong", {}, g.id)), h("td", {}, g.title), h("td", {}, g.text)))))),
    h("div", {class: "card"}, h("h3", {}, "Approved facts"), h("table", {}, h("thead", {}, h("tr", {}, ["ID", "Statement", "Source", "Valid until"].map((x) => h("th", {}, x)))), h("tbody", {}, k.facts.map((f) => h("tr", {}, h("td", {}, f.id), h("td", {}, f.statement), h("td", {}, f.source), h("td", {}, f.valid_until)))))),
    h("div", {class: "card"}, h("h3", {}, "Palette and assets"), h("p", {}, Object.entries(k.visual.palette).map(([n, v]) => h("span", {}, h("span", {class: "swatch", ref: v}), `${n} ${v}  `))), h("p", {}, "Approved assets: " + k.visual.assets.map((a) => `${a.filename} (${a.width}x${a.height})`).join(", "))));
  root.querySelectorAll(".swatch").forEach((s) => (s.style.background = s.getAttribute("ref")));
  if (S.user.role === "admin") {
    const ta = h("textarea", {id: "kitjson", "aria-label": "Brand kit JSON"}); ta.value = JSON.stringify(k, null, 2); ta.style.minHeight = "320px";
    root.append(h("div", {class: "card"}, h("h3", {}, "Edit brand kit (admin)"), ta, h("p", {}, h("button", {class: "btn", onclick: guard(async () => { await api("/api/brandkit", {method: "PUT", body: {kit: JSON.parse(ta.value), note: "Edited in UI"}}); toast("Saved as a new version", true); render(); })}, "Save new version"))));
  }
  return root;
}

async function viewAudit() {
  const d = await api("/api/audit");
  return h("div", {}, h("h2", {}, "Audit log"), h("div", {class: "card"}, h("table", {}, h("thead", {}, h("tr", {}, ["When", "User", "Action", "Item", "Detail"].map((x) => h("th", {}, x)))), h("tbody", {}, d.audit.map((a) => h("tr", {}, h("td", {}, fmt(a.ts)), h("td", {}, a.user), h("td", {}, a.action), h("td", {}, a.item_id ?? ""), h("td", {}, a.detail)))))));
}

async function viewDisclosure() {
  const d = await api("/api/disclosure");
  return h("div", {class: "card"}, h("h2", {}, "AI and data disclosure"), h("p", {}, h("strong", {}, "Automation: "), d.automation), h("p", {}, h("strong", {}, "External AI: "), d.ai.enabled ? `Enabled (${d.ai.provider}, model ${d.ai.model}). Sent: ${d.ai.sent}.` : "Off. " + d.ai.sent + "."), h("p", {}, h("strong", {}, "Storage: "), d.storage),
    h("p", {}, h("strong", {}, "External services: "), d.external_services.length ? d.external_services.join(", ") : "none in use"));
}

// ---------------------------------------------------------------- router
async function render() {
  const main = $("#main"); const [page, arg] = (location.hash.slice(1) || "items").split("/");
  if (!S.user && page !== "disclosure") { renderNav(); main.replaceChildren(viewLogin()); return; }
  renderNav(page);
  try {
    const v = page === "item" ? await viewItem(arg) : page === "new" ? viewNew() : page === "check" ? viewCheck() : page === "insights" ? await viewInsights()
      : page === "kit" ? await viewKit() : page === "audit" ? await viewAudit() : page === "disclosure" ? await viewDisclosure() : await viewItems();
    main.replaceChildren(v);
  } catch (e) { main.replaceChildren(h("div", {class: "card"}, h("p", {}, e.message))); }
}
window.addEventListener("hashchange", render);
render();
