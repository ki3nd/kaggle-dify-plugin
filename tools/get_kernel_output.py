from __future__ import annotations

import mimetypes
import os
import re
import tempfile
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

# Kaggle absolute path prefixes that are stripped to get the relative output path.
_KAGGLE_PATH_PREFIXES = (
    "/kaggle/working/",
    "/kaggle/output/",
    "/kaggle/",
)

# Statuses where the kernel has not finished successfully.
_RUNNING_STATUSES = {"running", "queued"}
_FAILED_STATUSES = {"error", "cancelacknowledged", "cancelled"}

_TEXT_EXTENSIONS = {
    ".csv", ".txt", ".log", ".md", ".py", ".html",
    ".xml", ".yaml", ".yml", ".svg", ".r", ".sh",
}
_JSON_EXTENSIONS = {".json", ".ipynb"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def _strip_kaggle_prefix(file_path: str) -> str:
    """Convert a Kaggle absolute path to a relative output path.

    Examples:
        /kaggle/working/output.csv  -> output.csv
        /kaggle/output/result.png   -> result.png
        /kaggle/result.csv          -> result.csv
        output.csv                  -> output.csv
    """
    normalized = file_path.strip()
    for prefix in _KAGGLE_PATH_PREFIXES:
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    # Already relative — strip leading slash if present.
    return normalized.lstrip("/")


def _find_target_file(outfiles: list[str], relative_path: str, log_path: str) -> str | None:
    """Return the downloaded file path matching relative_path, excluding the kernel log file."""
    for path in outfiles:
        if path == log_path:
            continue
        # Match by the relative_path suffix to handle any temp-dir prefix.
        if path.replace("\\", "/").endswith(relative_path.replace("\\", "/")):
            return path
    return None


def _yield_file(
    tool: Tool,
    file_path: str,
    relative_path: str,
) -> Generator[ToolInvokeMessage]:
    import json

    ext = os.path.splitext(relative_path)[1].lower()

    if ext in _IMAGE_EXTENSIONS:
        mime_type, _ = mimetypes.guess_type(relative_path)
        mime_type = mime_type or "image/png"
        with open(file_path, "rb") as f:
            data = f.read()
        yield tool.create_blob_message(data, meta={"mime_type": mime_type, "filename": relative_path})

    elif ext in _TEXT_EXTENSIONS:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        yield tool.create_text_message(content)

    elif ext in _JSON_EXTENSIONS:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        yield tool.create_json_message(parsed)

    else:
        # Unknown binary — send as blob.
        mime_type, _ = mimetypes.guess_type(relative_path)
        mime_type = mime_type or "application/octet-stream"
        with open(file_path, "rb") as f:
            data = f.read()
        yield tool.create_blob_message(data, meta={"mime_type": mime_type, "filename": relative_path})


class KaggleGetKernelOutputTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        kernel_id = str(tool_parameters.get("kernel_id", "")).strip()
        file_path = str(tool_parameters.get("file_path", "")).strip()

        relative_path: str | None = None
        if file_path:
            relative_path = _strip_kaggle_prefix(file_path)
            if not relative_path:
                raise ValueError(
                    f"file_path '{file_path}' resolves to an empty relative path. "
                    "Provide a specific file path, e.g. /kaggle/working/output.csv"
                )

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

        temp_root = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_root, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix="kaggle-output-", dir=temp_root
        ) as temp_dir:
            log_path = os.path.join(temp_dir, f"{kernel_slug}.log")

            if relative_path:
                # ── 2a. Download only the requested file ──────────────────────
                file_pattern = "^" + re.escape(relative_path) + "$"
                outfiles, _ = api.kernels_output(
                    normalized_kernel_id,
                    temp_dir,
                    file_pattern=file_pattern,
                    force=True,
                    quiet=True,
                )

                logs = read_log_file(log_path)
                target_file = _find_target_file(outfiles, relative_path, log_path)

                if target_file is None:
                    msg = f"File not found in kernel output: '{file_path}'."
                    if logs:
                        msg += f"\nKernel logs:\n{logs}"
                    yield self.create_text_message(msg)
                    return

                yield from _yield_file(self, target_file, relative_path)
                yield self.create_json_message(
                    {
                        "kernel_id": normalized_kernel_id,
                        "file_path": file_path,
                        "relative_path": relative_path,
                        "logs": logs,
                    }
                )
            else:
                # ── 2b. No file requested — return logs only ──────────────────
                outfiles, _ = api.kernels_output(
                    normalized_kernel_id,
                    temp_dir,
                    force=True,
                    quiet=True,
                )

                logs = read_log_file(log_path)
                yield self.create_json_message(
                    {
                        "kernel_id": normalized_kernel_id,
                        "logs": logs,
                    }
                )
