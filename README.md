# Researcher — Paper Search + Chat

Figma-style chat UI (Chat A.I.+) for searching open-access papers on **Google Scholar** and **IEEE Access**, then chatting from the **public abstract** via **Groq**.

## Stack

- **Frontend:** Vite + React (`frontend/`) — chat screen only
- **Backend:** FastAPI (`api/main.py`) wrapping search / clarify / chat
- **Branch:** `frontend-v1`

## Setup

```powershell
cd D:\Researcher
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `GROQ_API_KEY` in `.env`.

```powershell
cd frontend
npm install
```

## Run

Terminal 1 — API:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --reload --port 8000
```

Terminal 2 — UI:

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173

## Filters (brain icon)

In the message bar, click the **brain** icon to set:

- **Year**
- **Number of papers**

## Notes

- Open-access preference; no PDF download
- Chat answers use title + public abstract only
