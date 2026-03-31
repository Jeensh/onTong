# onTong

AI-powered Wiki Knowledge Management System for IT operations teams.

## Features

- **Markdown Wiki Editor** — Tiptap WYSIWYG editor with frontmatter metadata, WikiLinks, and slash commands
- **Multi-format Viewer** — Excel (edit/save), PDF, PowerPoint, Image (zoom/pan)
- **AI Copilot** — RAG-based Q&A with SSE streaming, source citations, and approval workflows
- **Skill System** — 6-layer structured prompts with trigger-based auto-matching
- **Hybrid Search** — BM25 + vector search with cross-encoder reranking
- **Document Conflict Detection** — Similarity-based duplicate detection, side-by-side diff, lineage tracking
- **Knowledge Graph** — Interactive document relationship visualization
- **Enterprise Ready** — RBAC, edit locking, Docker deployment, Redis state sharing, horizontal scaling

## Architecture

```
Frontend (Next.js 15)  ←→  Backend (FastAPI)  ←→  ChromaDB (Vector DB)
         ↕                        ↕
    Tiptap Editor           Ollama / OpenAI LLM
    react-force-graph       Redis (Lock/Cache)
```

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.10+
- Docker (for ChromaDB)

### Development

```bash
# 1. Backend
docker compose up -d chroma
python -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --port 8001 --reload

# 2. Frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:3000

### Docker (Production)

```bash
docker compose up -d
```

## Project Structure

```
backend/                 # FastAPI backend
├── api/                 # REST API routes
├── application/         # Business logic (agent, skill, wiki, conflict)
├── core/                # Auth, schemas, config
└── infrastructure/      # Storage, vector DB, search, cache

frontend/                # Next.js frontend
├── src/
│   ├── components/      # UI components
│   ├── editors/         # File type editors
│   └── lib/             # Utilities, stores, API clients

wiki/                    # Wiki content (file-based storage)
├── _skills/             # AI skill definitions
└── {folders}/           # Document categories

tests/                   # pytest test suite
```

## Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## License

MIT
