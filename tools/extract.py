from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import SLOW_TIMEOUT, SerpKiteError, boolean, call, compact, extract_markdown, integer, items, json_object, text


class SerpKiteExtractTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        urls = items(p, "urls", 20, label="URLs")
        if not urls:
            raise SerpKiteError("At least one URL is required.")
        body = compact({
            "urls": urls,
            "query": text(p, "query"),
            "highlights": integer(p, "highlights", 0, 10, label="Highlights") or None,
            "summary": boolean(p, "summary") or None,
            "output_schema": json_object(p, "output_schema", label="Output schema"),
            "prompt": text(p, "prompt"),
            "max_tokens": integer(p, "max_tokens", 100, 100000, label="Max tokens per page"),
            "country": text(p, "country"),
        })
        if body.get("highlights") and not body.get("query"):
            raise SerpKiteError("Highlights need a query to rank passages against.")
        result = call(self.runtime.credentials, "POST", "/v1/extract", body, timeout=SLOW_TIMEOUT)
        yield self.create_json_message(result)
        yield self.create_text_message(extract_markdown(result))
