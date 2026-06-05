# orellius-TCM

> [!IMPORTANT]
> **Archived April 2026. This project is no longer maintained.** Published as open source so others can study the architecture patterns.

A Telegram OSINT monitoring and content pipeline built to research how multi-agent LLM pipelines handle real-time signal translation, triage, and human-in-the-loop review at scale. The architecture explores how Tauri desktop apps can front-end Python agent backends, and how LangGraph orchestrates a multi-step review flow over streaming Telegram data.

---

## What this was

A desktop application that monitored a set of Telegram source channels, ran incoming messages through a local LLM translation and analysis pipeline, presented flagged content for human review, and published approved content to target channels - all from a single Tauri app backed by a FastAPI agent service.

**Research questions it was probing:**

- Can a LangGraph pipeline reliably triage high-velocity Telegram signal with minimal human attention?
- How does a Tauri desktop shell integrate with a Python async backend over WebSocket?
- What does real-time OSINT translation look like when the translation model is running locally (no API cost, no data egress)?
- How do you build a human review layer that doesn't become a bottleneck when signal volume spikes?

---

## Features

| Feature | Notes |
|---------|-------|
| Channel monitoring | Telethon MTProto, real-time message stream from N source channels |
| Translation pipeline | Ollama local inference (Qwen 2.5:32B for translation, Llama 3.3:70B for orchestration) |
| LangGraph review flow | Multi-step agent pipeline: ingest → translate → classify → human review → publish |
| Human review UI | Tauri frontend - approve, reject, or re-classify before publish |
| Watermark removal | Strips source channel watermarks from forwarded media |
| Stealth ghost monitoring | Monitor channels without appearing in the member list |
| RBAC | Role-based access for multi-operator setups |
| Vector memory | Qdrant for semantic dedup and context retrieval across sessions |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | Tauri 2, Rust |
| Frontend | React 19, Vite, TypeScript, Tailwind v4, Zustand |
| Agent backend | FastAPI (Python 3.12), LangGraph |
| Local inference | Ollama |
| Databases | PostgreSQL 16, Redis 7, Qdrant |
| Telegram | Telethon (MTProto) |
| Infrastructure | Docker Compose |

---

## Architecture

```
Telegram channels (MTProto via Telethon)
        │
        ▼
FastAPI + LangGraph pipeline
  ├── Ingest agent       - pulls messages, deduplicates via Qdrant
  ├── Translation agent  - Ollama local LLM, preserves structure
  ├── Classification     - flags by topic, urgency, source credibility
  └── Review queue       - holds messages for human decision
        │
        ▼
Tauri desktop app (WebSocket bridge)
  ├── Review panel       - approve / reject / reclassify
  └── Publish confirmed → target Telegram channel
```

The Tauri frontend communicates with the FastAPI backend over a local WebSocket. The pipeline is stateful - each message carries a lifecycle tag (ingest → translated → reviewed → published or rejected) persisted to PostgreSQL.

---

## Running it (for study purposes)

> [!NOTE]
> You will need a Telegram API ID and hash from [my.telegram.org](https://my.telegram.org), an Ollama instance with the relevant models pulled, and Docker for the database stack.

```bash
# 1. Copy and fill environment
cp .env.example .env

# 2. Start the backend stack
docker compose up -d

# 3. Install Python deps
cd backend && pip install -r requirements.txt

# 4. Start the FastAPI agent service
uvicorn main:app --reload

# 5. Start the Tauri app
bun install && bun run tauri:dev
```

---

## Responsible use

> [!WARNING]
> Use of this code to monitor Telegram channels must comply with [Telegram's Terms of Service](https://telegram.org/tos) and applicable law in your jurisdiction. The author assumes no responsibility for misuse.

This project was built for personal research into LLM agent pipelines and Telegram data processing architectures. It is published so others can study the patterns - LangGraph orchestration, Tauri↔Python WebSocket bridge, local LLM integration, and human-in-the-loop review design.

---

*Archived April 2026. See [Orellius](https://github.com/Orellius) for active work.*
