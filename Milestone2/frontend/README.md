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

Open **http://localhost:3000**. The UI calls `POST /query` on the FastAPI server.
