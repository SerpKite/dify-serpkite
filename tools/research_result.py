from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import research_markdown, integer, task_id, wait_for_task


class SerpKiteResearchResultTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        wait = integer(tool_parameters, "wait_seconds", 0, 240, label="Wait") or 0
        task = wait_for_task(self.runtime.credentials, f"/v1/research/{task_id(tool_parameters)}", wait)
        yield self.create_json_message(task)
        yield self.create_text_message(research_markdown(task))
