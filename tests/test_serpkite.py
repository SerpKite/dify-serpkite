import importlib
import pathlib
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
import yaml
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from provider.serpkite import SerpKiteProvider
from tools import common

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL_FILES = yaml.safe_load((ROOT / "provider/serpkite.yaml").read_text())["tools"]
TOOL_NAMES = [pathlib.Path(f).stem for f in TOOL_FILES]
CREDS = {"api_key": "skt_live_test"}


def response(payload=None, status=200, text=None, ctype="application/json"):
    r = Mock()
    r.status_code = status
    r.headers = {"Content-Type": ctype}
    r.json.return_value = payload
    if payload is None:
        r.json.side_effect = ValueError("not json")
    r.text = text
    return r


def run(name, params, reply):
    """Invokes a tool with a mocked HTTP reply; returns (request kwargs, messages)."""
    module = importlib.import_module(f"tools.{name}")
    cls = next(v for v in vars(module).values() if isinstance(v, type) and v.__module__ == module.__name__)
    tool = cls.__new__(cls)
    tool.runtime = SimpleNamespace(credentials=CREDS)
    tool.create_json_message = lambda data: ("json", data)
    tool.create_text_message = lambda text: ("text", text)
    with patch("tools.common.requests.request", return_value=reply) as req:
        messages = list(tool._invoke(params))
    return req.call_args, messages


def test_every_tool_is_declared_with_one_tool_class():
    assert len(TOOL_NAMES) == 23
    for name in TOOL_NAMES:
        spec = yaml.safe_load((ROOT / "tools" / f"{name}.yaml").read_text())
        assert spec["identity"]["name"] == name
        assert spec["extra"]["python"]["source"] == f"tools/{name}.py"
        module = importlib.import_module(f"tools.{name}")
        from dify_plugin import Tool

        classes = [v for v in vars(module).values() if isinstance(v, type) and v is not Tool and issubclass(v, Tool)]
        assert len(classes) == 1, name


def test_descriptions_link_pricing_without_hard_coded_credits():
    for name in TOOL_NAMES:
        spec = (ROOT / "tools" / f"{name}.yaml").read_text().lower()
        assert "credit" not in spec.replace("credits are returned", "") or name in ("search", "news", "extract"), name
        if not name.endswith("_result"):
            assert "serpkite.com/pricing" in spec, name
        for word in ("proxy", "proxies", "browser", "exit node", "residential"):
            assert word not in spec, (name, word)


def test_search_posts_json_body_with_bearer_and_keeps_json_default():
    payload = {"results": [{"title": "Example", "link": "https://example.com", "snippet": "Hi"}], "meta": {}}
    call, messages = run("search", {"query": "test", "country": "gb", "num": 20, "include_domains": "a.com, .gov", "output": None}, response(payload))
    args, kwargs = call
    assert args == ("POST", "https://api.serpkite.com/v1/search")
    assert kwargs["headers"]["Authorization"] == "Bearer skt_live_test"
    assert kwargs["json"] == {"q": "test", "country": "gb", "num": 20, "include_domains": ["a.com", ".gov"], "format": "json"}
    assert kwargs["timeout"] == common.FAST_TIMEOUT
    assert messages[0] == ("json", payload)
    assert "[Example](https://example.com)" in messages[1][1]


@pytest.mark.parametrize("name, path", [("images", "/v1/images"), ("videos", "/v1/videos"), ("shopping", "/v1/shopping"), ("scholar", "/v1/scholar"),
                                        ("patents", "/v1/patents"), ("autocomplete", "/v1/autocomplete"), ("maps", "/v1/maps")])
def test_verticals_return_server_markdown_by_default(name, path):
    call, messages = run(name, {"query": "coffee"}, response(text="# Results", ctype="text/markdown; charset=utf-8"))
    args, kwargs = call
    assert args == ("POST", "https://api.serpkite.com" + path)
    assert kwargs["json"] == {"q": "coffee", "format": "markdown"}
    assert messages == [("text", "# Results")]


@pytest.mark.parametrize("name", ["chatgpt", "gemini", "copilot", "ai_mode", "brave_ai"])
def test_assistants_use_long_timeout_and_track_list(name):
    params = {"prompt": "best crm", "country": "us", "track": "hubspot.com,\nPipedrive", "language": "en", "web_search": True}
    call, messages = run(name, params, response(text="Answer [1](https://x.com)", ctype="text/markdown"))
    args, kwargs = call
    assert args == ("POST", f"https://api.serpkite.com/v1/{name}")
    assert kwargs["timeout"] == common.SLOW_TIMEOUT >= 120
    body = kwargs["json"]
    assert body["prompt"] == "best crm" and body["track"] == ["hubspot.com", "Pipedrive"] and body["format"] == "markdown"
    assert ("web_search" in body) == (name == "chatgpt")
    assert ("language" in body) == (name != "chatgpt")
    assert messages == [("text", "Answer [1](https://x.com)")]


def test_assistant_json_output_renders_sources_and_mentions():
    payload = {"markdown": "Use HubSpot [1](https://hubspot.com)", "sources": [{"position": 1, "title": "HubSpot", "link": "https://hubspot.com"}],
               "mentions": [{"term": "hubspot.com", "mentioned": True}], "meta": {}}
    _, messages = run("brave_ai", {"prompt": "crm", "output": "json"}, response(payload))
    assert messages[0] == ("json", payload)
    assert "[1] [HubSpot](https://hubspot.com)" in messages[1][1]
    assert "hubspot.com: mentioned" in messages[1][1]


def test_assistant_late_answer_message_is_passed_through():
    error = {"error": {"code": "upstream_timeout", "message": "ChatGPT was still answering; send the same request again within 10 minutes to receive it; you were not charged"}}
    with pytest.raises(common.SerpKiteError) as e:
        run("chatgpt", {"prompt": "x"}, response(error, status=503))
    assert "upstream_timeout" in str(e.value) and "again within 10 minutes" in str(e.value)


def test_prompt_limits_fail_before_network():
    with patch("tools.common.requests.request") as req:
        with pytest.raises(common.SerpKiteError):
            common.assistant_body({"prompt": "x" * 4001})
        with pytest.raises(common.SerpKiteError):
            common.assistant_body({"prompt": "x", "track": ",".join(str(i) for i in range(21))})
        req.assert_not_called()


def test_extract_body_and_markdown():
    payload = {"results": [{"url": "https://a.com", "title": "A", "summary": "Short.", "markdown": "Body"}],
               "failed": [{"url": "https://b.com", "error": {"code": "upstream_error", "message": "blocked"}}], "meta": {}}
    call, messages = run("extract", {"urls": "https://a.com\nhttps://b.com", "summary": True, "output_schema": '{"type":"object"}'}, response(payload))
    body = call[1]["json"]
    assert body == {"urls": ["https://a.com", "https://b.com"], "summary": True, "output_schema": {"type": "object"}}
    assert call[1]["timeout"] == common.SLOW_TIMEOUT
    assert "Summary: Short." in messages[1][1] and "Could not read https://b.com: blocked" in messages[1][1]


def test_extract_rejects_bad_schema_and_highlights_without_query():
    with pytest.raises(common.SerpKiteError, match="JSON object"):
        run("extract", {"urls": "https://a.com", "output_schema": "not json"}, response({}))
    with pytest.raises(common.SerpKiteError, match="need a query"):
        run("extract", {"urls": "https://a.com", "highlights": 3}, response({}))


def test_answer_and_map():
    call, messages = run("answer", {"query": "why", "depth": "fast"}, response({"answer": "Because [1]", "citations": [{"index": 1, "title": "T", "link": "https://t.com"}]}))
    assert call[1]["json"] == {"q": "why", "depth": "fast"}
    assert messages[1][1].startswith("Because [1]") and "[1] T — https://t.com" in messages[1][1]
    call, messages = run("map", {"url": "https://a.com", "include_paths": "^/docs/"}, response({"results": [{"url": "https://a.com/docs/x", "title": "X"}]}))
    assert call[1]["json"] == {"url": "https://a.com", "include_paths": ["^/docs/"]}
    assert messages[1] == ("text", "- https://a.com/docs/x — X")


def test_place_needs_an_id():
    with pytest.raises(common.SerpKiteError, match="place ID"):
        run("place", {"country": "us"}, response({}))
    call, _ = run("place", {"place_id": "ChIJ1"}, response(text="# Place", ctype="text/markdown"))
    assert call[1]["json"] == {"place_id": "ChIJ1", "format": "markdown"}


def test_research_start_and_wait_until_completed():
    _, messages = run("research", {"input": "topic", "effort": "lite"}, response({"id": "0192-ab", "status": "queued"}))
    assert "0192-ab" in messages[1][1]
    states = [response({"id": "0192-ab", "status": "running", "progress": {"step": "searching"}}),
              response({"id": "0192-ab", "status": "completed", "result": {"report": "Report [1]", "sources": [{"index": 1, "title": "S", "link": "https://s.com"}]}})]
    clock = iter([0, 0, 6, 6])
    with patch("tools.common.requests.request", side_effect=states):
        task = common.wait_for_task(CREDS, "/v1/research/0192-ab", 60, sleep=lambda s: None, clock=lambda: next(clock))
    assert common.research_markdown(task).startswith("Report [1]")


def test_task_results_report_progress_and_failures():
    assert "running" in common.research_markdown({"status": "running", "progress": {"round": 1}})
    assert common.crawl_markdown({"status": "failed", "error": {"message": "robots.txt disallows"}}) == "Crawl failed: robots.txt disallows"
    md = common.crawl_markdown({"status": "completed", "result": {"pages": [{"url": "https://a.com", "title": "A", "markdown": "x" * 300_000}]}})
    assert md.startswith("Crawl completed: 1 pages.") and len(md) < 201_000
    with pytest.raises(common.SerpKiteError):
        common.task_id({"id": "../account"})


def test_crawl_result_without_wait_polls_once():
    call, messages = run("crawl_result", {"id": "0192-ab", "wait_seconds": 0}, response({"id": "0192-ab", "status": "queued"}))
    assert call[0] == ("GET", "https://api.serpkite.com/v1/crawl/0192-ab")
    assert "queued" in messages[1][1]


@pytest.mark.parametrize("num", [0, 101, 1.5, True, "ten"])
def test_invalid_count_never_calls_http(num):
    with patch("tools.common.requests.request") as req:
        with pytest.raises(common.SerpKiteError, match="integer from 1 to 100"):
            common.search_body({"query": "test", "num": num}, num=(1, 100))
        req.assert_not_called()


@pytest.mark.parametrize("params, credentials", [({"query": ""}, CREDS), ({"query": "test"}, {})])
def test_missing_required_values_fail_before_network(params, credentials):
    with patch("tools.common.requests.request") as req:
        with pytest.raises(common.SerpKiteError):
            common.call(credentials, "POST", "/v1/search", common.search_body(params))
        req.assert_not_called()


def test_network_errors_do_not_expose_keys_or_queries():
    with patch("tools.common.requests.request", side_effect=requests.ConnectionError("skt_live_test https://api.serpkite.com/v1/search?q=private")):
        with pytest.raises(common.SerpKiteError) as error:
            common.call(CREDS, "POST", "/v1/search", {"q": "private"})
    assert "skt_live_test" not in str(error.value) and "private" not in str(error.value)


def test_api_error_message_is_used_and_capped():
    with patch("tools.common.requests.request", return_value=response({"error": {"code": "insufficient_credits", "message": "x" * 900}}, status=402)):
        with pytest.raises(common.SerpKiteError) as error:
            common.call(CREDS, "POST", "/v1/search", {"q": "a"})
    assert str(error.value).startswith("SerpKite error 402 (insufficient_credits): ") and len(str(error.value)) < 560
    with patch("tools.common.requests.request", return_value=response(None, status=429, text="<html>")):
        with pytest.raises(common.SerpKiteError, match="Rate limit"):
            common.call(CREDS, "POST", "/v1/search", {"q": "a"})


def test_markdown_and_empty_results():
    assert common.markdown({"results": []}) == "No results found."
    rendered = common.markdown({"answer": {"text": "Short answer"}, "results": [{"title": "Ex [1]", "link": "https://e.com/(x)", "snippet": "S"}]})
    assert rendered.startswith("Short answer") and r"[Ex \[1\]](https://e.com/%28x%29)" in rendered


def test_provider_validation_uses_free_account_endpoint():
    provider = SerpKiteProvider()
    ok = Mock()
    with patch("provider.serpkite.requests.get", return_value=ok) as get:
        provider._validate_credentials(CREDS)
    assert get.call_args[0] == ("https://api.serpkite.com/v1/account",)
    with patch("provider.serpkite.requests.get", side_effect=requests.HTTPError("401")):
        with pytest.raises(ToolProviderCredentialValidationError):
            provider._validate_credentials(CREDS)
    with pytest.raises(ToolProviderCredentialValidationError):
        provider._validate_credentials({})
