from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils import build_authenticated_kaggle_api, build_kernel_metadata, fetch_kernel


class KaggleGetKernelMetadataTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        kernel_id = str(tool_parameters.get("kernel_id", "")).strip()
        api = build_authenticated_kaggle_api(str(self.runtime.credentials.get("api_token", "")).strip())
        response = fetch_kernel(api, kernel_id)
        metadata = build_kernel_metadata(response)

        yield self.create_json_message(metadata)
