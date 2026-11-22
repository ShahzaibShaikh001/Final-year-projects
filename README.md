# Research Paper Search + Chat (Groq)

Search open-access papers on **Google Scholar** and **IEEE Access**, open the links, and chat using the **public abstract** via **Groq**.

Simple design: **search + links + abstract chat**. No PDF download.

## Features

- Any research topic
- Groq clarifies vague prompts before searching
- Default **1** paper; set N (or say “5 papers” in the prompt)
- Year filter
- Open-access preference
- Chat from title / abstract / metadata only

> Full-text download for deeper summaries can be added later if a supervisor needs it.

## Setup

```powershell
cd D:\Researcher
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `GROQ_API_KEY` from [console.groq.com](https://console.groq.com/).

Optional:

- `SERPAPI_KEY` — better Google Scholar results
- `IEEE_API_KEY` — official IEEE Xplore API
- `CONTACT_EMAIL` — polite ID for free academic APIs (Crossref / OpenAlex)

Without optional keys, search still works via public fallbacks.

## Run

```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

## Project layout

```
app.py
src/
  config.py
  models.py
  chat/      # clarify + abstract chat
  search/    # Scholar + IEEE + merge
```
