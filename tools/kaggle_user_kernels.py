from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils import build_authenticated_kaggle_api, list_kernels


class KaggleUserKernelsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        kaggle_user = str(tool_parameters.get("kaggle_user", "")).strip() or None
        api = build_authenticated_kaggle_api(str(self.runtime.credentials.get("api_token", "")).strip())
        kernels = list_kernels(api, kaggle_user=kaggle_user)
        yield self.create_json_message({"kernels": kernels})
