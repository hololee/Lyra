from __future__ import annotations

import json
import os
import re
import uuid
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from langgraph.graph import END, StateGraph

MODEL_NAME = os.getenv("POC_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT_SEC = float(os.getenv("OLLAMA_TIMEOUT_SEC", "60"))


class ChatRequest(BaseModel):
    session_id: str
    message: str


class InfraConfigRequest(BaseModel):
    session_id: str
    target_mode: Literal["both", "host_only"] = "both"
    host_gpu_count: int = 1
    worker_gpu_count: int = 4
    language: Literal["ko", "en"] = "ko"


class ChatResponse(BaseModel):
    session_id: str
    model: str
    phase: str
    assistant: str
    goal: str
    draft: dict[str, Any]
    violations: list[str]
    infra: dict[str, Any]
    llm_used: bool = False
    llm_response: dict[str, Any] | None = None
    result: str | None = None
    error_code: str | None = None


@dataclass
class SessionData:
    phase: str = "discover"
    goal: str = ""
    draft: dict[str, Any] = field(
        default_factory=lambda: {
            "name": "",
            "image": "",
            "target": "",
            "gpu_count": None,
            "root_password": "",
            "ssh_port": None,
            "jupyter_port": None,
            "code_port": None,
            "enable_jupyter": True,
            "enable_code_server": True,
            "volumes": [],
            "purpose": "",
        }
    )
    infra: dict[str, Any] = field(
        default_factory=lambda: {
            "target_mode": "both",
            "host_gpu_count": 1,
            "worker_gpu_count": 4,
            "language": "ko",
        }
    )
    violations: list[str] = field(default_factory=list)
    last_proposal: str = ""
    history: list[dict[str, str]] = field(default_factory=list)


class TurnState(TypedDict, total=False):
    session: SessionData
    user_text: str
    llm_parsed: dict[str, Any] | None
    normalized_patch: dict[str, Any]
    proposal_built: bool
    assistant: str
    result: str | None
    error: str | None
    rejected_reasons: list[str]
    touched_fields: list[str]


app = FastAPI(title="Provisioning Agent POC (LangGraph)")
app.mount("/static", StaticFiles(directory="poc/static"), name="static")
SESSIONS: dict[str, SessionData] = {}


@app.get("/")
def root() -> FileResponse:
    return FileResponse("poc/static/index.html")


@app.post("/api/session/new")
def new_session() -> dict[str, Any]:
    sid = str(uuid.uuid4())
    SESSIONS[sid] = SessionData()
    return {"session_id": sid, "model": MODEL_NAME, "infra": SESSIONS[sid].infra}


@app.post("/api/session/reset")
def reset_session(payload: dict[str, str]) -> dict[str, Any]:
    sid = payload.get("session_id") or str(uuid.uuid4())
    SESSIONS[sid] = SessionData()
    return {"session_id": sid, "model": MODEL_NAME, "infra": SESSIONS[sid].infra}


@app.post("/api/session/infra")
def update_infra(payload: InfraConfigRequest) -> dict[str, Any]:
    session = SESSIONS.get(payload.session_id)
    if session is None:
        session = SessionData()
        SESSIONS[payload.session_id] = session
    session.infra = {
        "target_mode": payload.target_mode,
        "host_gpu_count": max(0, int(payload.host_gpu_count)),
        "worker_gpu_count": max(0, int(payload.worker_gpu_count)),
        "language": payload.language,
    }
    return {"session_id": payload.session_id, "infra": session.infra}


def _lang(session: SessionData) -> str:
    return "en" if session.infra.get("language") == "en" else "ko"


def _recent_history(session: SessionData, n: int = 8) -> str:
    lines: list[str] = []
    for item in session.history[-n:]:
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _parse_json_text(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return None
    try:
        parsed = json.loads(text[s : e + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _ollama_json(messages: list[dict[str, str]], temperature: float = 0.1) -> dict[str, Any] | None:
    body = {
        "model": MODEL_NAME,
        "stream": False,
        "format": "json",
        "messages": messages,
        "options": {"temperature": temperature},
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SEC) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    content = str(((payload.get("message") or {}).get("content")) or "")
    return _parse_json_text(content)


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _normalize_patch(raw: dict[str, Any], touched_fields: list[str] | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if not isinstance(raw, dict):
        return patch
    allowed = set(touched_fields or [])

    for key in ["name", "image", "root_password"]:
        if allowed and key not in allowed:
            continue
        v = raw.get(key)
        if isinstance(v, str) and v.strip():
            patch[key] = v.strip()

    target = str(raw.get("target") or "").strip().lower()
    if (not allowed or "target" in allowed) and target in {"host", "worker"}:
        patch["target"] = target

    purpose = str(raw.get("purpose") or "").strip().lower()
    if (not allowed or "purpose" in allowed) and purpose in {"training", "inference"}:
        patch["purpose"] = purpose

    for key in ["gpu_count", "ssh_port", "jupyter_port", "code_port"]:
        if allowed and key not in allowed:
            continue
        iv = _to_int(raw.get(key))
        if iv is not None:
            patch[key] = iv

    for key in ["enable_jupyter", "enable_code_server"]:
        if allowed and key not in allowed:
            continue
        if isinstance(raw.get(key), bool):
            patch[key] = raw[key]

    if not allowed or "volumes" in allowed:
        volumes = raw.get("volumes")
        normalized_vols: list[dict[str, str]] = []
        if isinstance(volumes, list):
            for item in volumes:
                host_path = ""
                container_path = ""
                if isinstance(item, str) and ":" in item:
                    left, right = item.split(":", 1)
                    host_path = left.strip()
                    container_path = right.strip()
                elif isinstance(item, dict):
                    host_path = str(item.get("host_path") or item.get("source") or "").strip()
                    container_path = str(item.get("container_path") or item.get("target") or "").strip()
                if host_path and container_path:
                    normalized_vols.append({"host_path": host_path, "container_path": container_path})
        if normalized_vols:
            patch["volumes"] = normalized_vols

    return patch


def _draft_machine_snapshot(session: SessionData) -> str:
    return json.dumps(session.draft, ensure_ascii=False, sort_keys=True)


def _build_recommendation(session: SessionData) -> None:
    goal = session.goal.lower()
    purpose = "training" if any(k in goal for k in ["train", "fine", "튜닝", "학습", "파인튜닝"]) else "inference"
    default_image = "nvidia/cuda:12.4.1-runtime-ubuntu22.04" if purpose == "training" else "python:3.11-slim"

    requested_gpu = 1 if purpose == "training" else 0
    host_cap = int(session.infra.get("host_gpu_count") or 0)
    worker_cap = int(session.infra.get("worker_gpu_count") or 0)
    mode = str(session.infra.get("target_mode") or "both")

    target = "host"
    if mode == "both" and requested_gpu > host_cap and worker_cap >= requested_gpu:
        target = "worker"

    safe_gpu = min(requested_gpu, host_cap if target == "host" else worker_cap)
    safe_gpu = max(0, safe_gpu)

    name_base = re.sub(r"[^a-zA-Z0-9-]+", "-", session.goal.strip().lower()).strip("-") or "env"

    session.draft.update(
        {
            "name": f"{name_base[:24]}-{str(uuid.uuid4())[:6]}",
            "image": default_image,
            "target": target,
            "gpu_count": safe_gpu,
            "root_password": "change-me-1234",
            "ssh_port": 22222,
            "jupyter_port": 28888,
            "code_port": 28080,
            "enable_jupyter": True,
            "enable_code_server": True,
            "volumes": [],
            "purpose": purpose,
        }
    )
    _sync_service_ports(session.draft)


def _sync_service_ports(draft: dict[str, Any]) -> None:
    if not draft.get("enable_jupyter", True):
        draft["jupyter_port"] = None
    elif draft.get("jupyter_port") is None:
        draft["jupyter_port"] = 28888

    if not draft.get("enable_code_server", True):
        draft["code_port"] = None
    elif draft.get("code_port") is None:
        draft["code_port"] = 28080


def _validate(session: SessionData) -> list[str]:
    d = session.draft
    errors: list[str] = []

    if not str(d.get("name") or "").strip():
        errors.append("name is required")
    if not str(d.get("image") or "").strip():
        errors.append("image is required")

    target = str(d.get("target") or "")
    if target not in {"host", "worker"}:
        errors.append("target must be host or worker")

    gpu = d.get("gpu_count")
    if not isinstance(gpu, int) or gpu < 0:
        errors.append("gpu_count must be >= 0")

    host_cap = int(session.infra.get("host_gpu_count") or 0)
    worker_cap = int(session.infra.get("worker_gpu_count") or 0)
    if target == "host" and isinstance(gpu, int) and gpu > host_cap:
        errors.append(f"gpu_count exceeds host capacity ({host_cap})")
    if target == "worker" and isinstance(gpu, int) and gpu > worker_cap:
        errors.append(f"gpu_count exceeds worker capacity ({worker_cap})")
    if target == "worker" and session.infra.get("target_mode") == "host_only":
        errors.append("worker target unavailable in current infra mode")

    if not str(d.get("root_password") or "").strip():
        errors.append("root_password is required")

    ports: list[tuple[str, Any]] = [("ssh_port", d.get("ssh_port"))]
    if d.get("enable_jupyter", True):
        ports.append(("jupyter_port", d.get("jupyter_port")))
    if d.get("enable_code_server", True):
        ports.append(("code_port", d.get("code_port")))

    active_values: list[int] = []
    for name, value in ports:
        if not isinstance(value, int) or not (1024 <= value <= 65535):
            errors.append(f"{name} must be 1024..65535")
        elif value in active_values:
            errors.append(f"{name} duplicates another port")
        else:
            active_values.append(value)

    return errors


def _llm_parse_user(session: SessionData, user_text: str) -> dict[str, Any] | None:
    lang = _lang(session)
    system = (
        "You are a provisioning intent parser. Return strict JSON only with keys:\n"
        "dialog_act, goal_update, patch, touched_fields, needs_recommendation, confirm, request_summary, question, smalltalk_reply\n"
        "- dialog_act: one of [goal, revise, confirm, clarify, chitchat]\n"
        "- goal_update: string or empty\n"
        "- patch: object with optional fields name,image,target,gpu_count,root_password,ssh_port,jupyter_port,code_port,enable_jupyter,enable_code_server,purpose\n"
        "- touched_fields: array of fields explicitly requested in THIS user turn only, subset of [name,image,target,gpu_count,root_password,ssh_port,jupyter_port,code_port,enable_jupyter,enable_code_server,purpose,volumes]\n"
        "- needs_recommendation: boolean\n"
        "- confirm: boolean\n"
        "- request_summary: boolean\n"
        "- question: optional one-line question\n"
        "- smalltalk_reply: short natural reply for chitchat/capability questions in requested language\n"
        "Rules:\n"
        "- Use target only as host|worker.\n"
        "- Use purpose only as training|inference.\n"
        "- Keep language aligned with infra.language.\n"
        "- Do not copy unchanged draft values into patch.\n"
        "- For volume mapping requests, use patch.volumes=[{host_path,container_path}] and include touched_fields=['volumes'].\n"
        "- Never invent host_path/container_path values.\n"
        "- If user asks persistence without explicit host and container paths, keep patch.volumes empty and ask clarification in question.\n"
        "- For dialog_act=confirm, return patch={} and touched_fields=[].\n"
    )
    user = (
        f"infra={json.dumps(session.infra, ensure_ascii=False)}\n"
        f"goal={session.goal}\n"
        f"draft={json.dumps(session.draft, ensure_ascii=False)}\n"
        f"history={_recent_history(session)}\n"
        f"language={lang}\n"
        f"user_message={user_text}\n"
    )
    return _ollama_json([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])


def _llm_render_reply(
    session: SessionData,
    parsed: dict[str, Any],
    event: str,
    violations: list[str] | None = None,
    rejected_reasons: list[str] | None = None,
) -> str:
    lang = _lang(session)
    payload = {
        "event": event,
        "language": lang,
        "goal": session.goal,
        "draft": session.draft,
        "violations": violations or [],
        "rejected_reasons": rejected_reasons or [],
        "question": parsed.get("question"),
        "smalltalk_reply": parsed.get("smalltalk_reply"),
        "table_appended": event in {"propose", "revise", "summary", "confirmed"},
    }
    system = (
        "You are a provisioning assistant response generator.\n"
        "Return strict JSON with one key only: assistant_reply (string).\n"
        "Rules:\n"
        "- Write in requested language.\n"
        "- Keep concise and actionable.\n"
        "- When event is summary/propose/revise, do NOT restate full configuration values.\n"
        "- When event is need_goal, respond naturally and ask for provisioning goal.\n"
        "- When event is need_goal_prompt, only ask for provisioning goal in one concise sentence.\n"
        "- When event is violation/rejected, explain the issue and ask for corrected value.\n"
        "- If dialog_act is chitchat and smalltalk_reply is present, preserve that tone.\n"
        "- Do not introduce or modify any concrete config values not present in draft.\n"
        "- All ports/password/paths/counts in assistant_reply must match draft exactly.\n"
        "- If table_appended=true, assume configuration table is shown below your reply.\n"
        "- If table_appended=true, avoid duplicate bullets/field lists.\n"
        "- For event in [propose, revise, summary], end with one direct question asking confirm or further edits.\n"
        "- For event=confirmed, provide one short completion sentence only.\n"
        "- Do not output markdown code fences.\n"
    )
    user = json.dumps(payload, ensure_ascii=False)
    out = _ollama_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    if not isinstance(out, dict):
        return ""
    reply = str(out.get("assistant_reply") or "").strip()
    return reply


def _to_display_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "-"
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                host = str(item.get("host_path") or "").strip()
                cont = str(item.get("container_path") or "").strip()
                if host and cont:
                    parts.append(f"`{host}` -> `{cont}`")
        return ", ".join(parts) if parts else "-"
    return str(value)


def _markdown_summary(session: SessionData, status: str | None = None) -> str:
    d = session.draft
    rows = [
        ("name", d.get("name")),
        ("image", d.get("image")),
        ("target", d.get("target")),
        ("gpu_count", d.get("gpu_count")),
        ("root_password", d.get("root_password")),
        ("ssh_port", d.get("ssh_port")),
        ("jupyter_port", d.get("jupyter_port") if d.get("enable_jupyter", True) else None),
        ("code_port", d.get("code_port") if d.get("enable_code_server", True) else None),
        ("enable_jupyter", d.get("enable_jupyter")),
        ("enable_code_server", d.get("enable_code_server")),
        ("volumes", d.get("volumes")),
    ]
    lines = ["| field | value |", "|---|---|"]
    if status:
        lines.append(f"| status | {status} |")
    for key, value in rows:
        lines.append(f"| {key} | {_to_display_value(value)} |")
    return "\n".join(lines)


def _render_or_machine(
    session: SessionData,
    parsed: dict[str, Any],
    event: str,
    violations: list[str] | None = None,
    rejected_reasons: list[str] | None = None,
) -> str:
    reply = _llm_render_reply(
        session,
        parsed,
        event=event,
        violations=violations,
        rejected_reasons=rejected_reasons,
    )
    if reply:
        return reply
    return json.dumps(
        {
            "event": event,
            "dialog_act": parsed.get("dialog_act"),
            "goal": session.goal,
            "draft": session.draft,
            "violations": violations or [],
            "rejected_reasons": rejected_reasons or [],
            "question": parsed.get("question"),
            "smalltalk_reply": parsed.get("smalltalk_reply"),
        },
        ensure_ascii=False,
    )


def _dedupe_table_preface(reply: str, fallback_question: str = "") -> str:
    lines = [ln.strip() for ln in str(reply or "").splitlines()]
    kept: list[str] = []
    for ln in lines:
        if not ln:
            continue
        low = ln.lower()
        if "목적" in ln or "goal" in low or "purpose" in low:
            continue
        if "|" in ln:
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            continue
        if re.match(r"^\s*\d+\.\s+", ln):
            continue
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_ ]{0,30}\s*:\s*.+$", ln):
            continue
        if re.match(r"^[가-힣A-Za-z0-9_ ]{1,20}\s*[:：]\s*.+$", ln):
            continue
        kept.append(ln)

    text = " ".join(kept).strip()
    if fallback_question and "?" not in text and "？" not in text:
        text = f"{text}\n{fallback_question}".strip() if text else fallback_question
    return text


def _node_parse(state: TurnState) -> TurnState:
    session = state["session"]
    parsed = _llm_parse_user(session, state["user_text"])
    if not isinstance(parsed, dict):
        state["error"] = "llm_parse_failed"
        return state
    state["llm_parsed"] = parsed
    touched_fields_raw = parsed.get("touched_fields")
    touched_fields: list[str] = []
    if isinstance(touched_fields_raw, list):
        valid = {
            "name",
            "image",
            "target",
            "gpu_count",
            "root_password",
            "ssh_port",
            "jupyter_port",
            "code_port",
            "enable_jupyter",
            "enable_code_server",
            "purpose",
            "volumes",
        }
        touched_fields = [str(v) for v in touched_fields_raw if isinstance(v, str) and str(v) in valid]
    state["touched_fields"] = touched_fields
    state["normalized_patch"] = _normalize_patch(
        parsed.get("patch") if isinstance(parsed.get("patch"), dict) else {},
        touched_fields=touched_fields,
    )
    return state


def _node_apply(state: TurnState) -> TurnState:
    session = state["session"]
    parsed = state.get("llm_parsed") or {}
    patch = state.get("normalized_patch") or {}
    rejected_reasons: list[str] = []
    act = str(parsed.get("dialog_act") or "").strip().lower()

    goal_update = str(parsed.get("goal_update") or "").strip()
    if goal_update and (not session.goal or session.phase == "discover"):
        session.goal = goal_update

    previous_draft = dict(session.draft)
    if act != "confirm" and patch:
        session.draft.update(patch)

    needs_rec = bool(parsed.get("needs_recommendation"))
    proposal_built = False
    has_core_draft = bool(session.draft.get("name")) and bool(session.draft.get("image")) and bool(session.draft.get("target"))
    should_recommend = session.goal and (not has_core_draft) and (needs_rec or not session.draft.get("image") or not session.draft.get("target"))
    if should_recommend:
        _build_recommendation(session)
        proposal_built = True

    _sync_service_ports(session.draft)

    target = str(session.draft.get("target") or "")
    gpu = session.draft.get("gpu_count")
    host_cap = int(session.infra.get("host_gpu_count") or 0)
    worker_cap = int(session.infra.get("worker_gpu_count") or 0)
    mode = str(session.infra.get("target_mode") or "both")
    if target == "worker" and mode == "host_only":
        session.draft["target"] = previous_draft.get("target")
        rejected_reasons.append("worker target unavailable in current infra mode")
    if isinstance(gpu, int):
        cap = host_cap if target == "host" else worker_cap if target == "worker" else None
        if isinstance(cap, int) and gpu > cap:
            session.draft["gpu_count"] = previous_draft.get("gpu_count")
            rejected_reasons.append(f"gpu_count exceeds {target} capacity ({cap})")

    state["proposal_built"] = proposal_built
    state["rejected_reasons"] = rejected_reasons
    return state


def _node_validate(state: TurnState) -> TurnState:
    session = state["session"]
    session.violations = _validate(session)
    return state


def _node_respond(state: TurnState) -> TurnState:
    session = state["session"]
    parsed = state.get("llm_parsed") or {}
    rejected_reasons = state.get("rejected_reasons") or []

    if state.get("error"):
        state["assistant"] = ""
        state["result"] = None
        return state

    act = str(parsed.get("dialog_act") or "").strip().lower()
    confirm_requested = bool(parsed.get("confirm")) and act == "confirm"
    request_summary = bool(parsed.get("request_summary"))
    patch = state.get("normalized_patch") or {}

    if not session.goal:
        session.phase = "discover"
        act = str(parsed.get("dialog_act") or "").strip().lower()
        smalltalk = str(parsed.get("smalltalk_reply") or "").strip()
        if act == "chitchat" and smalltalk:
            goal_prompt = _render_or_machine(session, parsed, event="need_goal_prompt")
            state["assistant"] = f"{smalltalk}\n{goal_prompt}".strip()
        else:
            state["assistant"] = _render_or_machine(session, parsed, event="need_goal")
        state["result"] = None
        return state

    if session.violations:
        session.phase = "revise"
        state["assistant"] = _render_or_machine(
            session, parsed, event="violation", violations=session.violations
        )
        state["result"] = None
        return state

    if rejected_reasons:
        session.phase = "revise"
        state["assistant"] = _render_or_machine(
            session, parsed, event="rejected", rejected_reasons=rejected_reasons
        )
        state["result"] = None
        return state

    if confirm_requested:
        session.phase = "done"
        reply = _render_or_machine(session, parsed, event="confirmed")
        table = _markdown_summary(session, status="success")
        state["assistant"] = f"{reply}\n\n{table}".strip()
        state["result"] = "success"
        return state

    if request_summary:
        reply = _render_or_machine(session, parsed, event="summary")
        reply = _dedupe_table_preface(reply, str(parsed.get("question") or "").strip())
        if not reply:
            reply = _render_or_machine(session, parsed, event="clarify")
        table = _markdown_summary(session)
        state["assistant"] = f"{reply}\n\n{table}".strip()
        state["result"] = None
        return state

    if state.get("proposal_built"):
        session.phase = "propose"
        reply = _render_or_machine(session, parsed, event="propose")
        reply = _dedupe_table_preface(reply, str(parsed.get("question") or "").strip())
        if not reply:
            reply = _render_or_machine(session, parsed, event="clarify")
        table = _markdown_summary(session)
        state["assistant"] = f"{reply}\n\n{table}".strip()
        state["result"] = None
        return state

    if patch:
        session.phase = "revise"
        reply = _render_or_machine(session, parsed, event="revise")
        reply = _dedupe_table_preface(reply, str(parsed.get("question") or "").strip())
        if not reply:
            reply = _render_or_machine(session, parsed, event="clarify")
        table = _markdown_summary(session)
        state["assistant"] = f"{reply}\n\n{table}".strip()
        state["result"] = None
        return state

    state["assistant"] = _render_or_machine(session, parsed, event="clarify")
    state["result"] = None
    return state


def _node_error(state: TurnState) -> TurnState:
    state["assistant"] = ""
    state["result"] = None
    return state


def _route_after_parse(state: TurnState) -> str:
    return "error" if state.get("error") else "apply"


def _build_graph():
    g = StateGraph(TurnState)
    g.add_node("parse", _node_parse)
    g.add_node("apply", _node_apply)
    g.add_node("validate", _node_validate)
    g.add_node("respond", _node_respond)
    g.add_node("error", _node_error)
    g.set_entry_point("parse")
    g.add_conditional_edges("parse", _route_after_parse, {"apply": "apply", "error": "error"})
    g.add_edge("apply", "validate")
    g.add_edge("validate", "respond")
    g.add_edge("respond", END)
    g.add_edge("error", END)
    return g.compile()


GRAPH = _build_graph()


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    session = SESSIONS.get(req.session_id)
    if session is None:
        session = SessionData()
        SESSIONS[req.session_id] = session

    user_text = req.message.strip()
    session.history.append({"role": "user", "content": user_text})

    out = GRAPH.invoke({"session": session, "user_text": user_text})
    assistant = str(out.get("assistant") or "")
    session.history.append({"role": "assistant", "content": assistant})

    parsed = out.get("llm_parsed") if isinstance(out.get("llm_parsed"), dict) else None
    error_code = str(out.get("error") or "") or None

    return ChatResponse(
        session_id=req.session_id,
        model=MODEL_NAME,
        phase=session.phase,
        assistant=assistant,
        goal=session.goal,
        draft=session.draft,
        violations=session.violations,
        infra=session.infra,
        llm_used=parsed is not None,
        llm_response=parsed,
        result=out.get("result"),
        error_code=error_code,
    )
