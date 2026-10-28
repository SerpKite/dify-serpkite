from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import SerpKiteError, call, compact, markdown, text, wants_json


class SerpKitePlaceTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        as_json = wants_json(tool_parameters)
        body = compact({
            "place_id": text(tool_parameters, "place_id"),
            "cid": text(tool_parameters, "cid"),
            "country": text(tool_parameters, "country"),
            "language": text(tool_parameters, "language"),
            "format": "json" if as_json else "markdown",
        })
        if "place_id" not in body and "cid" not in body:
            raise SerpKiteError("A place ID or CID from a Maps Search result is required.")
        result = call(self.runtime.credentials, "POST", "/v1/place", body)
        if as_json:
            yield self.create_json_message(result)
            yield self.create_text_message(markdown(result))
        else:
            yield self.create_text_message(result)
