from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import call, choice, compact, text


class SerpKiteResearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        body = compact({
            "input": text(p, "input", required=True, label="Research task"),
            "effort": choice(p, "effort", ("lite", "standard", "deep"), label="Effort"),
        })
        task = call(self.runtime.credentials, "POST", "/v1/research", body)
        yield self.create_json_message(task)
        yield self.create_text_message(
            f"Research started: task ID {task.get('id')} (status {task.get('status')}). "
            "Get the report with Get Research Result and this task ID."
        )
