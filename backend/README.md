# Backend — Travel Outfit Planning Assistant

Python / LangGraph backend: agents, tools, and Streamlit entry (Phase 5+).

## Setup

```bash
cd backend
uv sync --extra dev
cp .env.example .env
# Edit backend/.env with your API keys
```

### API Key 配置（重要）

本项目 **始终优先使用 `backend/.env`**，会自动覆盖 Windows/Cursor 里残留的系统级 `OPENAI_API_KEY` 等变量，无需每次手动 `Remove-Item Env:\OPENAI_API_KEY`。

只需维护一份配置：

```env
OPENAI_API_KEY=你的DeepSeek密钥
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

若仍报 401，在 UI 错误提示中查看 **Key 尾号** 是否与 `.env` 一致；也可运行：

```bash
uv run python -c "from src.config import reload_settings, key_fingerprint; print(key_fingerprint(reload_settings().openai_api_key))"
```

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Layout

```
backend/
├── app/                 # Streamlit entry (Phase 5+)
├── src/
│   ├── config.py
│   ├── graph/
│   │   ├── state.py     # PlanningState, Pydantic models
│   │   ├── report.py    # TravelReport assembly models
│   │   ├── nodes/       # 6 Agent nodes (Phase 3)
│   │   └── workflow.py  # LangGraph orchestration (Phase 4+)
│   ├── tools/           # onebound, weather, geocode, image_gen
│   ├── services/        # cache, product_matcher, llm
│   ├── prompts/         # trip, stylist, image prompt templates
│   └── ...
├── tests/
├── pyproject.toml
└── .env.example
```

## Phase 2 — Tool layer (standalone)

```python
from datetime import date
from src.tools.weather import fetch_daily_weather
from src.tools.onebound import search_taobao_items
from src.tools.image_gen import build_outfit_prompt, generate_outfit_look
from src.services.product_matcher import pick_top_n

# Weather (requires AMAP_API_KEY)
fetch_daily_weather("北京", date(2026, 6, 3), date(2026, 6, 7))

# Taobao search (requires ONEBOUND_KEY / ONEBOUND_SECRET)
search_taobao_items("女 防晒 衬衫", max_price=200)

# Image generation (Jimeng / Volcengine)
from src.tools.image_gen import build_outfit_prompt, generate_outfit_look

prompt = build_outfit_prompt(destination="大理", date="2026-07-10", ...)
generate_outfit_look(prompt)  # uses Jimeng 3.1 when VOLCENGINE_* keys are set
```

## Phase 3 — Agent nodes (mock / inject LLM)

```python
import src.graph
from src.graph.nodes import trip_node, weather_node, stylist_node, image_node, shopping_node, report_node
from src.graph.state import PlanningState, ChatMessage

state = PlanningState(messages=[ChatMessage(role="user", content="7月1-5日去东京")])
state = trip_node(state)       # LLM: set llm=... to mock in tests
state = weather_node(state)
state = stylist_node(state)
state = image_node(state)
state = shopping_node(state)
state = report_node(state)
print(state.report)
```

## Phase 4 — LangGraph workflow

```bash
# Full pipeline (requires LLM + API keys in .env)
uv run python -m src.graph.workflow --demo "7月10-12日去大理，休闲风，预算200"

# JSON output
uv run python -m src.graph.workflow --demo "..." --json

# Skip trip LLM: start from fixture trip/outfits, run weather→assets→report
uv run python -m src.graph.workflow --mock-fixture --demo "继续规划"
```

```python
from src.graph.workflow import run_planning

# Single turn
state = run_planning("7月10-12日去大理，休闲风")

# Multi-turn follow-up (when phase=COLLECTING)
if state.phase.value == "collecting":
    state = run_planning("大理，7月10日到12日", state=state)

print(state.report)
```

Graph: `trip → weather → stylist → assets (image ∥ shopping) → report`.  
When trip info is incomplete, the graph stops after `trip` until the user replies.

## Phase 5 — Streamlit UI

```bash
cd backend
uv run streamlit run app/main.py
```

Open the URL shown in the terminal (default `http://localhost:8501`).

- **Left panel**: chat with multi-turn trip collection
- **Right panel**: daily report tabs (weather → outfit → AI image → products)
- **Example trips** and **重新规划** in the header
- Backend entry: `run_planning()` from `src.graph.workflow`

Ensure `backend/.env` has LLM and API keys configured before running the full flow.

### Skip image generation (testing)

Add to `backend/.env` to skip Jimeng/DashScope calls and speed up planning:

```env
SKIP_IMAGE_GENERATION=true
```

Set to `false` or remove when you want AI outfit images again.
