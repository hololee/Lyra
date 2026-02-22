# POC Work Summary

## Scope
- Rebuilt provisioning chat POC with FastAPI + LangGraph.
- Added stateful multi-turn flow for goal-driven provisioning draft updates.
- Integrated local LLM parsing/rendering through Ollama.

## Core Architecture
- Backend: `poc/app.py`
  - Session store in memory
  - Graph nodes: parse -> apply -> validate -> respond
  - Endpoints:
    - `POST /api/session/new`
    - `POST /api/session/reset`
    - `POST /api/session/infra`
    - `POST /api/chat`
- Frontend: `poc/static/*`
  - Chat UI
  - Infra controls
  - Draft/violations/LLM debug views

## Key Improvements Applied
- Removed hardcoded user-facing response strings from runtime response flow.
- Added LLM-driven response rendering with machine fallback payload.
- Added touched-field based patch merge protection.
- Prevented draft reset by recommendation rebuild once core draft exists.
- Added volume patch normalization:
  - Supports `"/host:/container"` and object forms.
  - Stores normalized shape: `[{host_path, container_path}]`.
- Enforced confirm stability:
  - Confirm turn no longer mutates draft.
  - Confirm path sets `phase=done`, `result=success`.
- Synced service toggles and ports:
  - Disabled service => corresponding port cleared.
- Added fixed markdown summary table output for stable config visibility.
- Added frontend markdown table rendering.
- Added done-state action button in assistant message:
  - "생성하기" triggers full session reset.

## Known Limitations
- LLM may still produce stylistic noise in free-text response lines.
- Final source of truth remains `draft` state, not narrative text.
- Session state is memory-based (not persistent across server restart).

## Current Intent
- POC is intended for conversation-flow validation, not production provisioning.
- State safety and deterministic patch application were prioritized over full natural-language flexibility.
