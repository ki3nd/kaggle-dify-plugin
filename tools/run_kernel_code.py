from collections.abc import Generator
import json
import os
import tempfile
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils import (
    build_authenticated_kaggle_api,
    build_kernel_metadata,
    fetch_kernel,
    normalize_accelerator,
)


class KaggleRunKernelCodeTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        kernel_id = str(tool_parameters.get("kernel_id", "")).strip()
        code = str(tool_parameters.get("code", ""))
        if not code.strip():
            raise ValueError("code is required.")

        accelerator = normalize_accelerator(tool_parameters.get("accelerator"))
        api = build_authenticated_kaggle_api(str(self.runtime.credentials.get("api_token", "")).strip())
        response = fetch_kernel(api, kernel_id)

        code_file = f"{response.blob.slug}.py"
        metadata = build_kernel_metadata(
            response,
            code_file=code_file,
            language="python",
            kernel_type="script",
            accelerator=accelerator,
        )

        temp_root = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_root, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="kaggle-run-kernel-", dir=temp_root) as temp_dir:
            metadata_path = os.path.join(temp_dir, api.KERNEL_METADATA_FILE)
            code_path = os.path.join(temp_dir, code_file)

            with open(metadata_path, "w", encoding="utf-8") as file:
                json.dump(metadata, file, indent=2)
            with open(code_path, "w", encoding="utf-8", newline="\n") as file:
                file.write(code)

            push_result = api.kernels_push(temp_dir, acc=accelerator)

        yield self.create_json_message(
            {
                "kernel_id": metadata["id"],
                "accelerator": accelerator or "None",
                "code_file": code_file,
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
