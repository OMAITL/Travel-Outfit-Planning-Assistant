# Travel Outfit Planning Assistant

AI travel outfit planning with Multi-Agent orchestration (LangGraph) and Taobao product recommendations.

## Repository Layout

```
Travel Outfit Planning Assistant/
├── backend/             # Python / LangGraph / Streamlit (all application code)
├── docs/                # PRD, TECH-STACK, DEVELOPMENT-PLAN
└── README.md
```

## Quick Start

All Python development happens under `backend/`:

```bash
cd backend
uv sync --extra dev
cp .env.example .env
uv run pytest
uv run streamlit run app/main.py
```

See [backend/README.md](backend/README.md) for details.

## Docs

- [PRD](docs/PRD.md)
- [TECH-STACK](docs/TECH-STACK.md)
- [DEVELOPMENT-PLAN](docs/DEVELOPMENT-PLAN.md)
