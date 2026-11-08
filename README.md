# SafeHaven Pay

SafeHaven Pay is a merchant risk console for transaction-level holds. It uses PayPal's authorize-first flow so low-risk orders can be captured immediately while higher-risk orders remain in an isolated Micro-Pool until delivery evidence or human review clears them.

## What is implemented

- FastAPI backend with a PayPal sandbox adapter for Orders v2 create, authorize, capture, and void.
- Risk Agent with an OpenAI-compatible explanation layer, deterministic scoring, named features, and safe fallback levels.
- Micro-Pool ledger, proposal/approval workflow, signed carrier events, tamper-evident evidence chain, and telemetry.
- React merchant console with responsive dashboard, transaction grid, detail drawer, copilot, flash-sale simulator, evidence verification, and failure injection controls.
- Demo mode uses clearly labelled sandbox-safe data if `PAYPAL_CLIENT_ID` and `PAYPAL_SECRET` are not configured.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env`. PayPal secrets stay server-side. The frontend never receives the client secret.

## Required credentials for a real deployment

| Variable | Required | Purpose |
| --- | --- | --- |
| `PAYPAL_CLIENT_ID` | Yes | PayPal sandbox or live REST app client ID |
| `PAYPAL_SECRET` | Yes | PayPal REST app secret; server-side only |
| `PAYPAL_BASE_URL` | Yes | Sandbox is `https://api-m.sandbox.paypal.com`; live is `https://api-m.paypal.com` |
| `DATABASE_URL` | Yes for production | PostgreSQL connection string for orders, pools, evidence, and telemetry |
| `CARRIER_HMAC_SECRET` | Yes for signed carrier events | Shared secret used by the carrier simulator/webhook sender |
| `PAYPAL_WEBHOOK_ID` | Yes for verified PayPal webhooks | Webhook ID created in the PayPal Developer Dashboard |

`LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` enable the real OpenAI-compatible explanation layer. If the provider is unavailable, the deterministic risk engine remains active and the API reports that fallback honestly in `/healthz`. `ELASTIC_URL`/`ELASTIC_API_KEY` are reserved for external telemetry; the local telemetry fallback remains available.

Important: the current hackathon demo stores runtime state in memory so it can run immediately. Before production or a Render deployment, add the PostgreSQL schema and replace the in-memory collections in `backend/main.py` with database repositories. Do not put PayPal secrets, database passwords, or LLM keys in the frontend or commit them to Git.

## PayPal flow

The live adapter follows the official PayPal REST sequence: create an order with `intent=AUTHORIZE`, send the buyer to the returned approval URL, authorize the approved order, then capture or void the real authorization ID. The adapter is intentionally isolated in `backend/paypal.py`.

## Honest scope

When PayPal and LLM credentials are configured, the sandbox payment and AI explanation paths are live. Without them, the UI uses clearly labelled demo-safe and deterministic fallbacks. Risk labels are represented from synthetic named features for the hackathon. Carrier events are simulator calls to the signed endpoint. The mandate token is SafeHaven Pay's own demo design, not a PayPal standard.

PayPal marks are used for the payment integration context and remain PayPal property. SafeHaven Pay is an independent hackathon prototype and does not imply PayPal sponsorship or endorsement.
