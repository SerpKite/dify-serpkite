from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import call, compact, integer, items, map_markdown, text


class SerpKiteMapTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        body = compact({
            "url": text(p, "url", required=True, label="URL"),
            "search": text(p, "search"),
            "limit": integer(p, "limit", 1, 5000, label="Limit"),
            "include_paths": items(p, "include_paths", 20, label="Include paths"),
        })
        result = call(self.runtime.credentials, "POST", "/v1/map", body)
        yield self.create_json_message(result)
        yield self.create_text_message(map_markdown(result))
