# Submission checklist

What is in this package, and what the team must still do.

## Round 1: The Plan
| Requirement | Where |
|---|---|
| Problem, evidence, users, research plan, solution, workflow, features, stack, responsible design, dev plan, impact | Claude document "BrandSentinel – Round 1 Plan" (export to PDF/Word); summary in docs/ROUND1_PLAN.md |
| **Still to do** | Run the interviews and survey the plan lists, and add real findings. Fill the roles table with names. Note: the plan names React/FastAPI/Postgres, the build uses a dependency-free stack (explained in ROUND1_PLAN.md); update the plan if you want it to match. |

## Round 2: The Build
| Requirement | Where |
|---|---|
| Functional MVP | `python3 run.py` |
| Source repository | Push this folder to a public GitHub repo (commit history matters for the build-window rule) |
| Deployed link or clear demonstration | **Still to do:** deploy (Dockerfile provided; any container host) or record the demo; docs/DEMO_SCRIPT.md |
| Architecture and decisions | docs/ARCHITECTURE.md |
| APIs, models, datasets, libraries, services | docs/DISCLOSURES.md |
| User testing evidence | **Still to do:** run docs/USER_TESTING_KIT.md and record results |
| Team contributions | **Still to do:** docs/CONTRIBUTIONS.md |

## Round 3: The Finish
| Requirement | Where |
|---|---|
| Final product and repository | this folder |
| Demo video or live demo | **Still to do:** record using docs/DEMO_SCRIPT.md |
| Concise report | docs/FINAL_REPORT.md (turn into slides if the organiser wants a deck) |
| Testing and reliability evidence | docs/TESTING.md, tests/, evaluation/ |
| Privacy, security, accessibility, responsible design | docs/RESPONSIBLE_AI.md |
| Limitations and roadmap | docs/LIMITATIONS_ROADMAP.md |
| Participant and contribution details | **Still to do:** docs/CONTRIBUTIONS.md, DISCLOSURES.md build-window statement |

## Before you present
1. Click through the demo script once yourselves. The package was tested via unit tests, the API and a scripted Chromium run (docs/TESTING.md), but not with a screen reader or real users.
2. Make sure every team member can explain `engine.py` and the workflow rules in `server.py`.
3. Verify the statistics in the plan against their original sources.
