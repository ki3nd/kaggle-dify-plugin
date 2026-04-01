from collections.abc import Generator
import json
import os
import tempfile
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils import (
    DEFAULT_NEW_KERNEL_CODE,
    DEFAULT_NEW_KERNEL_CODE_FILE,
    build_authenticated_kaggle_api,
    initialize_new_kernel_metadata,
    normalize_kernel_title,
)


class KaggleCreateKernelTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        title = normalize_kernel_title(tool_parameters.get("title", ""))
        is_private = tool_parameters.get("is_private", True)
        enable_internet = tool_parameters.get("enable_internet", True)

        api = build_authenticated_kaggle_api(str(self.runtime.credentials.get("api_token", "")).strip())
        temp_root = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_root, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="kaggle-create-kernel-", dir=temp_root) as temp_dir:
            metadata = initialize_new_kernel_metadata(
                api,
                temp_dir,
                title=title,
                is_private=is_private,
                enable_internet=enable_internet,
                code_file=DEFAULT_NEW_KERNEL_CODE_FILE,
            )

            metadata_path = os.path.join(temp_dir, api.KERNEL_METADATA_FILE)
            with open(metadata_path, "w", encoding="utf-8") as file:
                json.dump(metadata, file, indent=2)

            code_path = os.path.join(temp_dir, DEFAULT_NEW_KERNEL_CODE_FILE)
            with open(code_path, "w", encoding="utf-8", newline="\n") as file:
                file.write(DEFAULT_NEW_KERNEL_CODE)

            push_result = api.kernels_push(temp_dir)

        yield self.create_json_message(
            {
                "kernel_id": metadata["id"],
                "kernel_name": metadata["title"],
                "code_file": metadata["code_file"],
                "metadata": metadata,
                "result": {
                    "url": getattr(push_result, "url", None),
                    "version_number": getattr(push_result, "versionNumber", None),
                    "error": getattr(push_result, "error", None),
                    "invalid_tags": getattr(push_result, "invalidTags", None),
                    "invalid_dataset_sources": getattr(push_result, "invalidDatasetSources", None),
                    "invalid_competition_sources": getattr(push_result, "invalidCompetitionSources", None),
                    "invalid_kernel_sources": getattr(push_result, "invalidKernelSources", None),
                },
            }
        )
