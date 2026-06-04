# Travel Outfit — Vue Frontend

Vue 3 + Vite + Pinia，对接 `backend/api`（FastAPI）。

## 开发

**终端 1 — API（在 `backend` 目录）：**

```bash
cd backend
uv sync --extra api
uv run uvicorn api.main:app --reload --port 8000
```

**终端 2 — 前端：**

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 。Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 构建

```bash
npm run build
npm run preview
```

生产环境可让 FastAPI 托管 `frontend/dist`，或单独部署静态站并配置 `VITE_API_BASE`。

## 页面

| 路由 | 说明 |
|------|------|
| `/` | v1 杂志风规划页（对照 `docs/prototypes/v1-travel-magazine.html`） |
| `/tryon` | v3 试衣占位（待接原型） |

## 与 Streamlit 的关系

`backend/app/main.py`（Streamlit）可保留作调试；日常开发请用本前端 + API。
