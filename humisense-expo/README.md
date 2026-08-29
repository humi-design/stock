# HUMISENSE — AI Operations Workforce

**Money Expo Mumbai · 29–30 August 2026 · Expo Demo Build**

> Your systems detect the problem. Humisense resolves it.

Humisense automates the expensive repetitive work that happens **after** a
financial system detects a mismatch: investigating the exception, checking
multiple systems, comparing records, finding evidence, determining root cause,
preparing a resolution and documenting everything — while keeping humans in
control of high-impact actions.

This repository is a **fast, simple, shared-hosting-compatible demo**. It is
not the full Humisense platform.

---

## What's inside

- **Reconciliation engine** — real, deterministic Python logic (pandas). AI is
  never used for financial calculations.
- **Deviation detection** — MISSING_TRANSACTION, DUPLICATE_TRANSACTION,
  AMOUNT_MISMATCH, DATE_MISMATCH, ACCOUNT_MISMATCH, STATUS_MISMATCH,
  SETTLEMENT_MISMATCH, UNMATCHED_TRANSACTION.
- **Synthetic data** — 12,842 bank records, 12,831 broker records, 12,796
  settlement records with 326 intentional exceptions. Fully offline.
- **Case Engine** — generic case model reusable by future agents
  (KYC, AML, Fraud, Settlement, Complaints, Compliance).
- **AI Gateway** — `mock` (default, offline, deterministic and data-driven),
  `openai_compatible` (OpenAI/OpenRouter/Ollama), and `gemini` adapter.
- **Human approval** — high-risk actions require confirmation. Actions are
  simulated; no real financial system is touched.
- **Audit trail** — every investigation and approved action is recorded.
- **ROI calculator** — directional estimate only, no guaranteed-savings claims.
- **Lead capture** — stored in MySQL or SQLite (automatic fallback).
- **Dark mode + responsive premium fintech UI** — Tailwind CDN, Inter font,
  Lucide icons, Chart.js (where useful).

## Quick start (development)

```bash
cd humisense-expo
pip install -r requirements.txt
python app.py            # http://127.0.0.1:5000
```

No AI API key needed. `DEMO_MODE=true` and the `mock` AI provider are the
defaults, so the app runs fully offline.

## Demo flow

1. Landing → **Start Live Demo** → AI Operations Control Center
2. **Run Reconciliation** → 12,842 records → 326 exceptions
3. **View Exceptions** → CASE #82931 (₹184,500 settlement exception)
4. **Investigate with Humisense** → evidence → root cause → 94% confidence
5. **Recommended Resolution** → human approval modal
6. **Case Resolved** → audit trail → ROI → **Book Pilot**

Use **Start 3-Minute Demo** on the Control Center for a stage-by-stage guided
walkthrough the presenter can pause at any point.

## Configuration

Copy `.env.example` to `.env` and adjust.

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask sessions | demo key |
| `DB_HOST` | MySQL host. **Leave empty = SQLite** | *(empty)* |
| `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | MySQL connection | — |
| `AI_PROVIDER` | `mock` · `openai_compatible` · `gemini` | `mock` |
| `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` | Live AI settings | — |
| `DEMO_MODE` | Demo mode | `true` |

Switching between MySQL and SQLite is a single setting (`DB_HOST`). SQLite
tables are created automatically. MySQL users can import `schema.sql`.

## Security notes

- Live API keys are stored masked, never rendered in full, and never logged.
- The AI cannot execute SQL or Python. It only produces investigation text.
- High-risk actions always require human approval.
- All demo data is synthetic; all resolution actions are simulated.

## Deployment

See [README_DEPLOYMENT.md](README_DEPLOYMENT.md) for cPanel / Passenger
instructions.