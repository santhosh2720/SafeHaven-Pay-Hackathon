# SafeHaven Pay

SafeHaven Pay is a merchant risk console for transaction-level holds. It uses PayPal's authorize-first flow so low-risk orders can be captured immediately while higher-risk orders remain in an isolated Micro-Pool until delivery evidence or human review clears them.

## What is implemented

- FastAPI backend with a PayPal sandbox adapter for Orders v2 `AUTHORIZE`, authorization capture, and void.
- Risk Agent with deterministic rules, named features, SHAP-style contribution bars, and fallback levels.
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

Optional integrations are `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` for LLM phrasing, and `ELASTIC_URL`/`ELASTIC_API_KEY` for external telemetry. The deterministic risk engine and Postgres telemetry fallback should remain available if either provider is unavailable.

Important: the current hackathon demo stores runtime state in memory so it can run immediately. Before production or a Render deployment, add the PostgreSQL schema and replace the in-memory collections in `backend/main.py` with database repositories. Do not put PayPal secrets, database passwords, or LLM keys in the frontend or commit them to Git.

## PayPal flow

The live adapter follows the official PayPal REST sequence: create an order with `intent=AUTHORIZE`, authorize after buyer approval, then capture or void the resulting authorization. The adapter is intentionally isolated in `backend/paypal.py` so sandbox credentials can be added without changing product logic.

## Honest scope

PayPal sandbox operations, the risk pipeline, evidence chain, telemetry, and approval workflow are real. Risk labels are trained/represented from synthetic named features for the hackathon. Carrier events are simulator calls to the signed endpoint. The mandate token is SafeHaven Pay's own demo design, not a PayPal standard.

PayPal marks are used for the payment integration context and remain PayPal property. SafeHaven Pay is an independent hackathon prototype and does not imply PayPal sponsorship or endorsement.
