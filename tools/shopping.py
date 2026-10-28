from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import call, markdown, search_body, wants_json


class SerpKiteShoppingTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        as_json = wants_json(tool_parameters, "markdown")
        body = search_body(tool_parameters, extra=('location', 'page'))
        body["format"] = "json" if as_json else "markdown"
        result = call(self.runtime.credentials, "POST", "/v1/shopping", body)
        if as_json:
            yield self.create_json_message(result)
            yield self.create_text_message(markdown(result))
        else:
            yield self.create_text_message(result)
