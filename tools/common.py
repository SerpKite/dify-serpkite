"""Shared request, parameter and Markdown helpers for the SerpKite tools.

Every tool module defines exactly one Tool subclass (Dify loads the single subclass
per file), so the shared logic lives here as plain functions.
"""

import json
import time
from typing import Any, Callable

import requests

API = "https://api.serpkite.com"

# Seconds to wait for a response. AI assistants, answers and AI extraction take up to
# 90 s on the API side, so they get extra headroom.
FAST_TIMEOUT = 90
SLOW_TIMEOUT = 150

TIME_RANGES = ("hour", "day", "week", "month", "year")


class SerpKiteError(ValueError):
    """An error message that is safe to show to the user and the model."""


def api_key(credentials: dict[str, Any]) -> str:
    key = credentials.get("api_key")
    if not isinstance(key, str) or not key.strip():
        raise SerpKiteError("A SerpKite API key is required.")
    return key.strip()


def call(
    credentials: dict[str, Any],
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: int = FAST_TIMEOUT,
) -> Any:
    """Calls the API. Returns parsed JSON, or the text body for Markdown responses."""
    key = api_key(credentials)
    try:
        response = requests.request(
            method,
            API + path,
            headers={"Authorization": f"Bearer {key}", "User-Agent": "serpkite-dify/0.1.0"},
            json=body,
            timeout=timeout,
        )
    except requests.Timeout:
        raise SerpKiteError("SerpKite did not answer in time. Try again.") from None
    except requests.RequestException:
        raise SerpKiteError("Could not reach SerpKite. Check the network and try again.") from None
    if response.status_code >= 400:
        raise SerpKiteError(error_message(response))
    if "markdown" in response.headers.get("Content-Type", ""):
        return response.text
    try:
        return response.json()
    except ValueError:
        raise SerpKiteError("SerpKite returned a response that is not JSON.") from None


def error_message(response: requests.Response) -> str:
    """The API's error message ({"error":{"code","message"}}), never the key or the query URL."""
    code, message = "", ""
    try:
        error = response.json().get("error") or {}
        code, message = str(error.get("code") or ""), str(error.get("message") or "")
    except (ValueError, AttributeError):
        pass
    if not message:
        message = {
            401: "The API key is missing or invalid.",
            402: "Not enough credits.",
            429: "Rate limit reached. Try again shortly.",
        }.get(response.status_code, "The request failed.")
    label = f"SerpKite error {response.status_code}" + (f" ({code})" if code else "")
    return f"{label}: {message[:500]}"


# ── Parameters ──────────────────────────────────────────────────────────


def text(params: dict[str, Any], name: str, required: bool = False, label: str | None = None) -> str | None:
    value = params.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value not in (None, "") and not isinstance(value, str):
        raise SerpKiteError(f"{label or name} must be text.")
    if required:
        raise SerpKiteError(f"{label or name} is required.")
    return None


def integer(params: dict[str, Any], name: str, low: int, high: int, label: str | None = None) -> int | None:
    value = params.get(name)
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            value = None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value) or not low <= value <= high:
        raise SerpKiteError(f"{label or name} must be an integer from {low} to {high}.")
    return int(value)


def boolean(params: dict[str, Any], name: str) -> bool | None:
    value = params.get(name)
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def items(params: dict[str, Any], name: str, limit: int, label: str | None = None) -> list[str] | None:
    """A list from a comma- or newline-separated string (or a list)."""
    value = params.get(name)
    if value is None or value == "":
        return None
    if isinstance(value, str):
        parts = value.replace("\n", ",").split(",")
    elif isinstance(value, list):
        parts = [str(v) for v in value]
    else:
        raise SerpKiteError(f"{label or name} must be a comma-separated list.")
    out = [p.strip() for p in parts if p.strip()]
    if len(out) > limit:
        raise SerpKiteError(f"{label or name} takes at most {limit} entries.")
    return out or None


def json_object(params: dict[str, Any], name: str, label: str | None = None) -> dict | None:
    value = params.get(name)
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict):
        raise SerpKiteError(f"{label or name} must be a JSON object (a JSON Schema).")
    return parsed


def choice(params: dict[str, Any], name: str, options: tuple[str, ...], label: str | None = None) -> str | None:
    value = text(params, name)
    if value is not None and value not in options:
        raise SerpKiteError(f"{label or name} must be one of: {', '.join(options)}.")
    return value


def compact(body: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in body.items() if v is not None}


def wants_json(params: dict[str, Any], default: str = "markdown") -> bool:
    return (text(params, "output") or default) == "json"


# ── Request bodies ──────────────────────────────────────────────────────


def search_body(params: dict[str, Any], *, num: tuple[int, int] | None = None, extra: tuple[str, ...] = ()) -> dict:
    """Body for the search verticals. `extra` names the optional fields a vertical takes."""
    body: dict[str, Any] = {
        "q": text(params, "query", required=True, label="Query"),
        "country": text(params, "country"),
        "language": text(params, "language"),
    }
    if num:
        body["num"] = integer(params, "num", num[0], num[1], label="Number of results")
    if "location" in extra:
        body["location"] = text(params, "location")
    if "time" in extra:
        body["time"] = choice(params, "time", TIME_RANGES, label="Time range")
    if "page" in extra:
        body["page"] = integer(params, "page", 1, 10, label="Page")
    if "domains" in extra:
        body["include_domains"] = items(params, "include_domains", 20, label="Include domains")
        body["exclude_domains"] = items(params, "exclude_domains", 20, label="Exclude domains")
    if "include_answer" in extra:
        body["include_answer"] = boolean(params, "include_answer")
    return compact(body)


def assistant_body(params: dict[str, Any], *, web_search: bool = False, language: bool = True) -> dict:
    prompt = text(params, "prompt", required=True, label="Prompt")
    if len(prompt) > 4000:
        raise SerpKiteError("The prompt can be at most 4,000 characters.")
    body: dict[str, Any] = {
        "prompt": prompt,
        "country": text(params, "country"),
        "track": items(params, "track", 20, label="Track"),
    }
    if language:
        body["language"] = text(params, "language")
    if web_search:
        body["web_search"] = boolean(params, "web_search")
    return compact(body)


# ── Markdown ────────────────────────────────────────────────────────────


def _link(title: Any, link: Any) -> str:
    title = str(title or "Untitled").replace("[", r"\[").replace("]", r"\]")
    link = str(link or "").replace("(", "%28").replace(")", "%29")
    return f"[{title}]({link})" if link else title


def markdown(payload: dict) -> str:
    """Short Markdown of a JSON search response: the answer (if any) and numbered results."""
    lines = []
    answer = payload.get("answer")
    if isinstance(answer, dict) and answer.get("text"):
        lines += [str(answer["text"]), ""]
    elif isinstance(answer, str) and answer:
        lines += [answer, ""]
    results = payload.get("results") or []
    if not results and not lines:
        return "No results found."
    for index, item in enumerate(results, 1):
        if not isinstance(item, dict):
            lines.append(f"{index}. {item}")
            continue
        lines.append(f"{index}. {_link(item.get('title') or item.get('value') or item.get('name'), item.get('link') or item.get('url') or item.get('website'))}")
        detail = item.get("snippet") or item.get("address") or item.get("source")
        if detail:
            lines.append(str(detail))
        lines.append("")
    return "\n".join(lines).rstrip()


def assistant_markdown(payload: dict) -> str:
    lines = [str(payload.get("markdown") or payload.get("text") or "_No answer._"), ""]
    sources = [s for s in payload.get("sources") or [] if isinstance(s, dict)]
    if sources:
        lines.append("Sources:")
        lines += [f"[{s.get('position', i)}] {_link(s.get('title'), s.get('link') or s.get('url'))}" for i, s in enumerate(sources, 1)]
    mentions = [m for m in payload.get("mentions") or [] if isinstance(m, dict)]
    if mentions:
        lines += ["", "Mentions:"]
        lines += [f"- {m.get('term')}: {'mentioned' if m.get('mentioned') else 'not mentioned'}" for m in mentions]
    return "\n".join(lines).rstrip()


def webpage_markdown(payload: dict) -> str:
    title = (payload.get("metadata") or {}).get("title") if isinstance(payload.get("metadata"), dict) else None
    head = f"# {title}\n{payload.get('url', '')}\n\n" if title else ""
    return head + str(payload.get("markdown") or payload.get("text") or "_The page has no readable content._")


def answer_markdown(payload: dict) -> str:
    out = []
    if payload.get("output") is not None:
        out.append("```json\n" + json.dumps(payload["output"], indent=2, ensure_ascii=False) + "\n```")
    elif payload.get("answer") is None:
        out.append("_No answer: the search found nothing to answer from._")
    else:
        out.append(str(payload["answer"]))
    cites = [c for c in payload.get("citations") or [] if isinstance(c, dict)]
    if cites:
        out.append("Sources:\n" + "\n".join(f"[{c.get('index')}] {c.get('title', '')} — {c.get('link', '')}" for c in cites))
    return "\n\n".join(out)


def extract_markdown(payload: dict) -> str:
    out = []
    for r in payload.get("results") or []:
        part = [f"# {r.get('title') or r.get('url')}\n{r.get('url', '')}"]
        if r.get("summary"):
            part.append("Summary: " + str(r["summary"]))
        if r.get("output") is not None:
            part.append("```json\n" + json.dumps(r["output"], indent=2, ensure_ascii=False) + "\n```")
        elif r.get("highlights"):
            part += ["> " + str(h.get("text", "")).replace("\n", "\n> ") for h in r["highlights"] if isinstance(h, dict)]
        else:
            part.append(str(r.get("markdown") or r.get("text") or ""))
        out.append("\n\n".join(p for p in part if p))
    for f in payload.get("failed") or []:
        error = f.get("error") or {}
        out.append(f"_Could not read {f.get('url')}: {error.get('message', 'failed')}_")
    return "\n\n".join(out) or "_No pages were read._"


def map_markdown(payload: dict) -> str:
    lines = []
    for r in payload.get("results") or []:
        line = "- " + str(r.get("url", ""))
        if r.get("title"):
            line += " — " + str(r["title"])
        lines.append(line)
    return "\n".join(lines) or "_No URLs found._"


# ── Async tasks (crawl, research) ───────────────────────────────────────

FINISHED = ("completed", "failed", "canceled")

# The text of a crawl result is capped: it goes into a model's context.
CRAWL_CHARS = 200_000


def wait_for_task(
    credentials: dict[str, Any],
    path: str,
    wait: int,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """GETs the task, re-polling every 5 s until it finishes or `wait` seconds pass."""
    deadline = clock() + wait
    while True:
        task = call(credentials, "GET", path)
        if task.get("status") in FINISHED or clock() + 5 > deadline:
            return task
        sleep(5)


def task_id(params: dict[str, Any]) -> str:
    value = text(params, "id", required=True, label="Task ID")
    if not all(c.isalnum() or c == "-" for c in value) or len(value) > 64:
        raise SerpKiteError("Task ID must be the id returned when the task was started.")
    return value


def task_pending(kind: str, task: dict) -> str | None:
    """A status line for a task without a result, or None when it has one."""
    status = str(task.get("status", ""))
    if isinstance(task.get("result"), dict) and status == "completed":
        return None
    error = task.get("error")
    if isinstance(error, dict) and error.get("message"):
        return f"{kind} {status}: {error['message']}"
    if status in FINISHED and not task.get("result"):
        return f"{kind} {status}."
    if status in FINISHED:
        return None
    progress = json.dumps(task.get("progress") or {})
    return f"{kind} is {status or 'queued'}; progress {progress}. Get the result again shortly with the same task ID."


def crawl_markdown(task: dict) -> str:
    pending = task_pending("Crawl", task)
    if pending:
        return pending
    pages = [p for p in (task.get("result") or {}).get("pages") or [] if isinstance(p, dict)]
    out = [f"Crawl {task.get('status')}: {len(pages)} pages."]
    size = len(out[0])
    for i, page in enumerate(pages):
        left = CRAWL_CHARS - size
        if left <= 0:
            out.append(f"_{len(pages) - i} more pages are in the JSON output._")
            break
        body = str(page.get("markdown") or page.get("text") or "")
        if len(body) > left:
            body = body[:left] + "…"
        chunk = f"# {page.get('title') or page.get('url')}\n{page.get('url', '')}\n\n{body}"
        out.append(chunk)
        size += len(chunk)
    return "\n\n".join(out)


def research_markdown(task: dict) -> str:
    pending = task_pending("Research", task)
    if pending:
        return pending
    result = task.get("result") or {}
    out = [str(result.get("report") or "")]
    sources = [s for s in result.get("sources") or [] if isinstance(s, dict)]
    if sources:
        out.append("## Sources\n" + "\n".join(f"[{s.get('index')}] {s.get('title', '')} — {s.get('link', '')}" for s in sources))
    return "\n\n".join(out)
