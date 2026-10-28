from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import call, compact, boolean, text, wants_json, webpage_markdown


class SerpKiteWebpageTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        as_json = wants_json(tool_parameters)
        body = compact({
            "url": text(tool_parameters, "url", required=True, label="URL"),
            "country": text(tool_parameters, "country"),
            "include_links": boolean(tool_parameters, "include_links") or None,
            "format": "json" if as_json else "markdown",
        })
        result = call(self.runtime.credentials, "POST", "/v1/webpage", body)
        if as_json:
            yield self.create_json_message(result)
            yield self.create_text_message(webpage_markdown(result))
        else:
            yield self.create_text_message(result)
