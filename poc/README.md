# LangGraph Provisioning POC

## Run

```bash
python3 -m uvicorn poc.app:app --host 127.0.0.1 --port 8800
```

Open: `http://127.0.0.1:8800`

## What it does

- Asks for your provisioning goal.
- Loads infra state (host/worker GPU capacity).
- Proposes a full configuration matching the goal + infra.
- Lets you revise options in chat.
- Validates constraints and asks for fixes when needed.
- Confirms final plan.

## Notes

- Model is controlled by `POC_MODEL` (default `qwen3:4b-instruct-2507-q4_K_M`).
- Ollama endpoint: `OLLAMA_BASE_URL`.
- Timeout: `OLLAMA_TIMEOUT_SEC`.
