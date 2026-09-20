# Info System Agent

Info System Agent is a local-first application for generating lightweight internal information systems.

Info System Agent generates lightweight internal information systems from plain-language business requirements.

It is built for HR, operations, administration, founders, and business managers who need practical systems for low-frequency workflows but cannot justify expensive custom development. Examples include office-supply management, resume tracking, attendance records, asset registers, internal request tracking, and simple department databases.

## Why it exists

Many companies do not lack information-management needs. They lack an economical way to build small systems. A traditional outsourced project can cost tens of thousands of dollars even when the workflow is simple and low-frequency. Info System Agent lowers that threshold by turning a short requirement description into a working admin system that users can inspect and refine.

## What it does

- Understands the business goal from natural language.
- Proposes modules and fields for the information system.
- Supports YOLO mode for fully automated generation.
- Supports HITL mode for business-user review and feedback.
- Generates a Flask-Admin application with models, views, configuration, and startup files.
- Runs validation, semantic review, launch testing, and auto-fix loops.
- Provides a browser preview of the generated system.

## Architecture

```text
FastAPI + static web UI
  -> TinyDB session manager
  -> LangGraph workflow
  -> OpenAI-compatible provider
  -> Jinja2 code generator
  -> Flask-Admin generated project
  -> Preview manager
```

## Project structure

```text
backend/              FastAPI app and API routes
frontend/templates/   Static HTML UI
agent/                LangGraph workflow, nodes, provider, state
codegen/              Jinja2 templates and generator
shared/               Session and preview managers
docs/                 Product and architecture documentation
bin/ops.sh            Local process helper
```

## Quick start

```bash
uv sync --all-extras
cp .env.example .env
# edit .env and set OPENAI_API_KEY
uv run uvicorn oma_info_system.api.app:app --host 127.0.0.1 --port 8020
```

Open `http://127.0.0.1:8020`.

## Environment

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
DATA_DIR=./data
HOST=127.0.0.1
PORT=8020
DEBUG=false
```

When `DATA_DIR` is omitted, the application uses the repository's `data/` directory. TinyDB stores session history and system settings in `data/app.json`; preview state, generated projects, traces, and service logs remain under that same root.

## API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/config` | Public feature config |
| POST | `/api/sessions` | Create a generation session |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}` | Get session status |
| GET | `/api/sessions/{id}/trace` | Get session execution trace |
| POST | `/api/sessions/{id}/approve` | Continue HITL workflow |
| POST | `/api/sessions/{id}/preview` | Start generated app preview |

## Deployment

Recommended production command:

```bash
uv run uvicorn oma_info_system.api.app:app --host 127.0.0.1 --port 8020
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full text.
