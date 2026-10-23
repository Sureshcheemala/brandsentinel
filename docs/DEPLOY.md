# Deploying BrandSentinel

Any container host works (Render, Railway, Fly.io, Cloud Run). The `Dockerfile` listens on `PORT`.

| Setting | Value | Notes |
|---|---|---|
| Start command | `python3 run.py` (default in the Dockerfile) | |
| `PORT` | set by the host | |
| `BS_HOST` | `0.0.0.0` | already set in the Dockerfile |
| `BS_DB` | `/data/brandsentinel.db` | mount a disk at `/data` to keep data between restarts; without one, data resets on restart (fine for a demo) |
| `BS_DEMO_PASSWORD` | leave unset for `demo123` | the one-click demo buttons assume `demo123` |
| `BS_EXTERNAL_AI` | `on` to enable the AI review | off by default |
| `ANTHROPIC_API_KEY` | your key, as a **secret/environment variable** | never commit it; it is read only from the environment |
| `BS_AI_MODEL` | optional | default `claude-sonnet-5-5` |

After deploying: open the URL in a private window, click a demo account, then (with AI on) review a draft and look for findings labelled "AI-assisted". Check `/api/health` returns `{"ok": true}`. To seed demo activity for the Insights page run `python3 seed_demo.py` against the live URL only if you want sample history (it creates synthetic items).
