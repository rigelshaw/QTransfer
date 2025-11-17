# QTransfer — Quantum-Secure File Transfer

**Tagline:** *Wormhole meets Quantum — future-proof file sharing*

QTransfer is a production-quality demo that simulates BB84 quantum key distribution (QKD), derives AES-GCM keys, and enables encrypted file transfer with real-time QBER visualization and Eve simulation. It’s built for demos, teaching, and research extension.

## Live demo
*(link to your deployment or “Local dev only”)*
- Frontend: Vercel / local `npm run dev`
- Backend: FastAPI (local `uvicorn backend.app.main:app --reload`)
- Qiskit Service: Dockerized Aer simulator (optional)

## Features
- BB84 QKD simulation (local Aer or analytic fast-mode)
- Real-time QBER visualization via WebSockets
- AES-GCM 256-bit encryption with HKDF-SHA256 key derivation
- Chunked file uploads (streaming encryption) & one-time links
- Eve simulations (intercept-resend / passive)
- Audit PDF report generation
- OpenAPI spec and example client snippets
- Docker + Docker Compose for local dev
- CI with GitHub Actions, tests: PyTest + Jest

## Quick start (local)
> Prereqs: Node 18+, Python 3.11+, Docker (optional), git

**Backend**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# API docs at http://localhost:8000/docs
