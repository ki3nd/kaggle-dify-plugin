from __future__ import annotations

import os
import tempfile
import zipfile
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils import (
    build_authenticated_kaggle_api,
    fetch_kernel_status,
    parse_kernel_id,
    read_log_file,
    serialize_api_value,
)

_RUNNING_STATUSES = {"running", "queued"}
_FAILED_STATUSES = {"error", "cancelacknowledged", "cancelled"}


class KaggleDownloadKernelOutputTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        kernel_id = str(tool_parameters.get("kernel_id", "")).strip()

        api = build_authenticated_kaggle_api(
            str(self.runtime.credentials.get("api_token", "")).strip()
        )

        owner = api.config_values.get(api.CONFIG_NAME_USER)
        owner_slug, kernel_slug = parse_kernel_id(kernel_id, owner=owner)
        normalized_kernel_id = f"{owner_slug}/{kernel_slug}"

        # ── 1. Check kernel status ────────────────────────────────────────────
        status_response = fetch_kernel_status(api, normalized_kernel_id)
        status_details = serialize_api_value(status_response)
        status: str = ""
        failure_message: str = ""
        if isinstance(status_details, dict):
            status = str(status_details.get("status") or "").strip()
            failure_message = str(status_details.get("failureMessage") or "").strip()

        status_lower = status.lower()

        if status_lower in _RUNNING_STATUSES:
            yield self.create_text_message(
                f"Kernel is still {status}. Wait for it to complete and retry."
            )
            return

        if status_lower in _FAILED_STATUSES:
            msg = f"Kernel failed with status: {status}."
            if failure_message:
                msg += f"\nFailure message: {failure_message}"
            yield self.create_text_message(msg)
            return

        if status_lower != "complete":
            yield self.create_text_message(
                f"Unexpected kernel status: '{status}'. "
                f"Details: {status_details}"
            )
            return

        # ── 2. Download all output files ──────────────────────────────────────
        temp_root = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_root, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix="kaggle-download-", dir=temp_root
        ) as temp_dir:
            log_path = os.path.join(temp_dir, f"{kernel_slug}.log")

            outfiles, _ = api.kernels_output(
                normalized_kernel_id,
                temp_dir,
                force=True,
                quiet=True,
            )

            # ── 3. Separate logs from output files ────────────────────────────
            log_content = read_log_file(log_path)
            output_files = [p for p in outfiles if p != log_path]

            if not output_files:
                yield self.create_text_message(
                    "Kernel completed but produced no output files."
                )
                yield self.create_json_message(
                    {
                        "kernel_id": normalized_kernel_id,
                        "logs": log_content,
                        "files": [],
                    }
                )
                return

            # ── 4. Package all output files into a zip ────────────────────────
            zip_name = f"{kernel_slug}-output.zip"
            zip_path = os.path.join(temp_dir, zip_name)

            archived_files: list[str] = []
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in output_files:
                    arcname = os.path.relpath(file_path, temp_dir)
                    zf.write(file_path, arcname)
                    archived_files.append(arcname)

            with open(zip_path, "rb") as f:
                zip_data = f.read()

            yield self.create_blob_message(
                zip_data,
                meta={"mime_type": "application/zip", "filename": zip_name},
            )
            yield self.create_json_message(
                {
                    "kernel_id": normalized_kernel_id,
                    "zip_file": zip_name,
                    "files": archived_files,
                    "logs": log_content,
                }
            )
