from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import SLOW_TIMEOUT, assistant_body, assistant_markdown, call, wants_json


class SerpKiteAIModeTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        as_json = wants_json(tool_parameters)
        body = assistant_body(tool_parameters, web_search=False, language=True)
        body["format"] = "json" if as_json else "markdown"
        result = call(self.runtime.credentials, "POST", "/v1/ai_mode", body, timeout=SLOW_TIMEOUT)
        if as_json:
            yield self.create_json_message(result)
            yield self.create_text_message(assistant_markdown(result))
        else:
            yield self.create_text_message(result)
