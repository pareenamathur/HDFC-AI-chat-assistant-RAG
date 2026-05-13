# Next.js frontend (API on FastAPI)

## Prerequisite

Install **Node.js LTS** (includes `npm`). This folder did not ship with `package.json` historically; it is restored for local dev.

## Setup

```bash
cd frontend
npm install
```

Copy `.env.local` (points `NEXT_PUBLIC_API_URL` at `http://localhost:8000`) or set your own.

## Run (with backend on port 8000)

```bash
npm run dev
```

Open **http://localhost:3000**. The UI calls `GET /health` and `POST /query` on the FastAPI server.

## Vercel + Railway

1. In **Vercel → Project → Settings → Environment Variables**, set `NEXT_PUBLIC_API_URL` to your **HTTPS** Railway URL (no trailing slash), then redeploy.
2. On **Railway**, set `CORS_ALLOW_ORIGINS` to your Vercel site origin (e.g. `https://your-app.vercel.app`) or `*` while debugging browser CORS errors.
3. If the UI shows a yellow banner about `NEXT_PUBLIC_API_URL`, the production build was deployed without that variable.
