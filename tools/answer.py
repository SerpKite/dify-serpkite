from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import SLOW_TIMEOUT, TIME_RANGES, answer_markdown, call, choice, compact, integer, items, text


class SerpKiteAnswerTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        body = compact({
            "q": text(p, "query", required=True, label="Question"),
            "depth": choice(p, "depth", ("fast", "standard"), label="Depth"),
            "num_sources": integer(p, "num_sources", 1, 5, label="Sources to read"),
            "country": text(p, "country"),
            "language": text(p, "language"),
            "time": choice(p, "time", TIME_RANGES, label="Time range"),
            "include_domains": items(p, "include_domains", 20, label="Include domains"),
            "exclude_domains": items(p, "exclude_domains", 20, label="Exclude domains"),
        })
        result = call(self.runtime.credentials, "POST", "/v1/answer", body, timeout=SLOW_TIMEOUT)
        yield self.create_json_message(result)
        yield self.create_text_message(answer_markdown(result))
