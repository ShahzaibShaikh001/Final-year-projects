# Researcher — Paper Search + Chat

Search open-access papers on **Google Scholar** and **IEEE Access**, then chat from the **public abstract** using **Groq**.

## Branches

| Branch | What it contains |
|--------|------------------|
| **`v1`** | Backend only — FastAPI (`api/`), search/chat logic (`src/`), `requirements.txt` |
| **`frontend-v1`** | Frontend + full stack for local demos — React chat UI (`frontend/`) plus the same API |

UI matches the Figma Chat A.I.+ chat screen. Use the **brain** icon in the message bar for **Year** and **Number of papers**.

---

## 1. Backend (`v1`)

```powershell
git checkout v1
cd D:\Researcher
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set:

```
GROQ_API_KEY=your_key_here
```

Start the API:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: http://127.0.0.1:8000/api/health

---

## 2. Frontend (`frontend-v1`)

In another terminal (same repo after switching branch, or a second clone/worktree):

```powershell
git checkout frontend-v1
cd D:\Researcher\frontend
npm install
npm run dev
```

Open: **http://localhost:5173**

The Vite app proxies `/api` → `http://127.0.0.1:8000`, so the backend must be running.

---

## Run both together (recommended for demo)

**Easiest:** stay on `frontend-v1` (it includes API + UI).

```powershell
git checkout frontend-v1
```

Terminal 1 — backend:

```powershell
cd D:\Researcher
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```powershell
cd D:\Researcher\frontend
npm install
npm run dev
```

Then open **http://localhost:5173**.

### Optional: two worktrees (backend on `v1`, UI on `frontend-v1`)

```powershell
cd D:\Researcher
git worktree add D:\Researcher-v1 v1
git worktree add D:\Researcher-fe frontend-v1
```

- API from `D:\Researcher-v1`
- UI from `D:\Researcher-fe\frontend`

---

## How to use

1. Click the **brain** icon → set **Year** and **Number of papers**
2. Type a topic (e.g. “latest papers in radiology”)
3. Select a paper from the results
4. Ask for a summary (answers use the public abstract only)

---

## Project layout

```
api/main.py          # FastAPI routes
src/                 # Search, clarify, Groq chat
frontend/            # Vite + React chat UI  (frontend-v1)
.env.example
requirements.txt
```

## Notes

- Open-access preference; no PDF download in v1
- Optional keys: `SERPAPI_KEY`, `IEEE_API_KEY`, `CONTACT_EMAIL` (see `.env.example`)
