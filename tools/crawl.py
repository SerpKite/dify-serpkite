from typing import Any, Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.common import call, compact, integer, items, text


class SerpKiteCrawlTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        body = compact({
            "url": text(p, "url", required=True, label="Start URL"),
            "limit": integer(p, "limit", 1, 1000, label="Page limit"),
            "max_depth": integer(p, "max_depth", 0, 10, label="Max depth"),
            "query": text(p, "query"),
            "include_paths": items(p, "include_paths", 20, label="Include paths"),
            "exclude_paths": items(p, "exclude_paths", 20, label="Exclude paths"),
        })
        task = call(self.runtime.credentials, "POST", "/v1/crawl", body)
        yield self.create_json_message(task)
        yield self.create_text_message(
            f"Crawl started: task ID {task.get('id')} (status {task.get('status')}). "
            "Get the pages with Get Crawl Result and this task ID."
        )
