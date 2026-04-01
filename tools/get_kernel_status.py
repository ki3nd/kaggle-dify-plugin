from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils import (
    build_authenticated_kaggle_api,
    build_kernel_metadata,
    fetch_kernel,
    fetch_kernel_status,
    serialize_api_value,
)


class KaggleGetKernelStatusTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        kernel_id = str(tool_parameters.get("kernel_id", "")).strip()
        api = build_authenticated_kaggle_api(str(self.runtime.credentials.get("api_token", "")).strip())

        kernel_response = fetch_kernel(api, kernel_id)
        metadata = build_kernel_metadata(kernel_response)
        status_response = fetch_kernel_status(api, kernel_id)
        status_details = serialize_api_value(status_response)
        status = None
        if isinstance(status_details, dict):
            status = status_details.get("status")

        yield self.create_json_message(
            {
                "kernel_id": metadata["id"],
                "status": status,
                "status_details": status_details,
                "metadata": metadata,
            }
        )
