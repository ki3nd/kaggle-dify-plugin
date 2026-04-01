from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from typing import Any, Iterator


VALID_ACCELERATORS = (
    "NvidiaTeslaP100",
    "NvidiaTeslaT4",
    "TpuV5E8",
)
DEFAULT_NEW_KERNEL_CODE_FILE = "main.py"
DEFAULT_NEW_KERNEL_CODE = 'print("Hello, world!")\n'
DEFAULT_KERNELS_PAGE_SIZE = 100
_ACCELERATOR_UNSET = object()


@contextmanager
def _temporary_env_var(name: str, value: str) -> Iterator[None]:
    old_value = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if old_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old_value


def build_authenticated_kaggle_api(api_token: str):
    """
    Build and authenticate KaggleApi from a provided token.

    Notes:
    - We set KAGGLE_API_TOKEN before lazy import because current kaggle package
      may authenticate during import-time side effects.
    - Environment is restored after auth to avoid leaking process state.
    """
    token = (api_token or "").strip()
    if not token:
        raise ValueError("KAGGLE_API_TOKEN is required.")

    with _temporary_env_var("KAGGLE_API_TOKEN", token):
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()
        return api


def parse_kernel_id(kernel_id: str) -> tuple[str, str]:
    normalized_kernel_id = str(kernel_id or "").strip()
    if not normalized_kernel_id:
        raise ValueError("kernel_id is required.")
    if "/" not in normalized_kernel_id:
        raise ValueError("kernel_id must be in the format 'owner/kernel-slug'.")

    owner_slug, kernel_slug = normalized_kernel_id.split("/", 1)
    if not owner_slug or not kernel_slug:
        raise ValueError("kernel_id must be in the format 'owner/kernel-slug'.")
    return owner_slug, kernel_slug


def normalize_kernel_title(title: Any) -> str:
    normalized_title = str(title or "").strip()
    if not normalized_title:
        raise ValueError("title is required.")
    if len(normalized_title) < 5:
        raise ValueError("title must be at least 5 characters long.")
    return normalized_title


def slugify_kernel_title(title: str) -> str:
    normalized_title = normalize_kernel_title(title)
    try:
        from slugify import slugify as kaggle_slugify

        slug = str(kaggle_slugify(normalized_title)).strip()
    except ImportError:
        slug = re.sub(r"[^a-z0-9]+", "-", normalized_title.lower()).strip("-")
    if not slug:
        raise ValueError("title must contain at least one letter or number.")
    return slug


def get_authenticated_username(api: Any) -> str:
    get_config_value = getattr(api, "get_config_value", None)
    if callable(get_config_value):
        username = str(get_config_value("username") or "").strip()
        if username:
            return username

    config_values = getattr(api, "config_values", None)
    if isinstance(config_values, dict):
        username = str(config_values.get("username") or "").strip()
        if username:
            return username

    raise ValueError("Could not determine the authenticated Kaggle username.")


def list_kernels(
    api: Any,
    *,
    kaggle_user: str | None = None,
    page_size: int = DEFAULT_KERNELS_PAGE_SIZE,
) -> list[dict[str, str]]:
    normalized_page_size = int(page_size)
    if normalized_page_size <= 0:
        raise ValueError("page_size must be >= 1.")

    normalized_kaggle_user = str(kaggle_user or "").strip() or None
    kernels: list[dict[str, str]] = []
    page = 1
    while True:
        page_items = api.kernels_list(
            page=page,
            page_size=normalized_page_size,
            mine=normalized_kaggle_user is None,
            user=normalized_kaggle_user,
        ) or []

        for item in page_items:
            if item is None:
                continue

            kernel_id = str(getattr(item, "ref", "") or "").strip()
            kernel_name = str(getattr(item, "title", "") or "").strip()
            if not kernel_id:
                continue

            kernels.append(
                {
                    "kernel_id": kernel_id,
                    "kernel_name": kernel_name,
                }
            )

        if len(page_items) < normalized_page_size:
            break
        page += 1

    return kernels


def ensure_unique_kernel_title(api: Any, title: str) -> None:
    normalized_title = normalize_kernel_title(title)
    normalized_slug = slugify_kernel_title(normalized_title)
    existing_kernels = list_kernels(api)
    existing_kernel_names = {item["kernel_name"].casefold() for item in existing_kernels if item.get("kernel_name")}
    existing_kernel_slugs = {
        slugify_kernel_title(item["kernel_name"])
        for item in existing_kernels
        if item.get("kernel_name")
    }
    if normalized_title.casefold() in existing_kernel_names:
        raise ValueError(
            f"A kernel with title '{normalized_title}' already exists, please change kernel title name."
        )
    if normalized_slug in existing_kernel_slugs:
        raise ValueError(
            f"A kernel with slug '{normalized_slug}' already exists, please change kernel title name."
        )


def fetch_kernel(api: Any, kernel_id: str) -> Any:
    owner_slug, kernel_slug = parse_kernel_id(kernel_id)
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

    with api.build_kaggle_client() as kaggle:
        request = ApiGetKernelRequest()
        request.user_name = owner_slug
        request.kernel_slug = kernel_slug
        return kaggle.kernels.kernels_api_client.get_kernel(request)


def fetch_kernel_status(api: Any, kernel_id: str) -> Any:
    normalized_kernel_id = "/".join(parse_kernel_id(kernel_id))
    return api.kernels_status(normalized_kernel_id)


def default_kernel_code_file(response: Any) -> str:
    language = str(response.blob.language).lower()
    kernel_type = str(response.blob.kernel_type).lower()
    slug = str(response.blob.slug)
    if kernel_type == "notebook":
        return f"{slug}.ipynb" if language == "python" else slug
    return f"{slug}.py" if language == "python" else slug


def normalize_accelerator(accelerator: Any) -> str | None:
    raw_value = str(accelerator or "").strip()
    if not raw_value or raw_value.lower() == "none":
        return None
    if raw_value not in VALID_ACCELERATORS:
        valid_values = ", ".join(["None", *VALID_ACCELERATORS])
        raise ValueError(f"accelerator must be one of: {valid_values}.")
    return raw_value


def accelerator_settings(accelerator: str | None) -> tuple[bool, bool, str | None]:
    normalized_accelerator = normalize_accelerator(accelerator)
    if normalized_accelerator is None:
        return False, False, None
    if normalized_accelerator == "TpuV5E8":
        return False, True, normalized_accelerator
    return True, False, normalized_accelerator


def build_kernel_metadata(
    response: Any,
    *,
    code_file: str | None = None,
    language: str | None = None,
    kernel_type: str | None = None,
    accelerator: str | None | object = _ACCELERATOR_UNSET,
) -> dict[str, Any]:
    server_metadata = response.metadata
    metadata: dict[str, Any] = {
        "id": server_metadata.ref,
        "id_no": server_metadata.id,
        "title": server_metadata.title,
        "code_file": code_file or default_kernel_code_file(response),
        "language": language or server_metadata.language,
        "kernel_type": kernel_type or server_metadata.kernel_type,
        "is_private": server_metadata.is_private,
        "enable_gpu": server_metadata.enable_gpu,
        "enable_tpu": server_metadata.enable_tpu,
        "enable_internet": server_metadata.enable_internet,
        "keywords": server_metadata.category_ids,
        "dataset_sources": server_metadata.dataset_data_sources,
        "competition_sources": server_metadata.competition_data_sources,
        "kernel_sources": server_metadata.kernel_data_sources,
        "model_sources": server_metadata.model_data_sources,
        "docker_image": server_metadata.docker_image,
        "machine_shape": server_metadata.machine_shape,
    }

    if accelerator is not _ACCELERATOR_UNSET:
        enable_gpu, enable_tpu, machine_shape = accelerator_settings(accelerator)
        metadata["enable_gpu"] = enable_gpu
        metadata["enable_tpu"] = enable_tpu
        metadata["machine_shape"] = machine_shape

    return metadata


def serialize_api_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): serialize_api_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize_api_value(item) for item in value]

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return serialize_api_value(to_dict())

    from_dict = getattr(value, "__dict__", None)
    if isinstance(from_dict, dict) and from_dict:
        return {
            str(key): serialize_api_value(item)
            for key, item in from_dict.items()
            if not str(key).startswith("_")
        }

    return str(value)


def initialize_new_kernel_metadata(
    api: Any,
    temp_dir: str,
    *,
    title: str,
    is_private: bool = True,
    enable_internet: bool = True,
    code_file: str = DEFAULT_NEW_KERNEL_CODE_FILE,
) -> dict[str, Any]:
    normalized_title = normalize_kernel_title(title)
    ensure_unique_kernel_title(api, normalized_title)
    api.kernels_initialize(temp_dir)

    metadata_path = os.path.join(temp_dir, api.KERNEL_METADATA_FILE)
    if not os.path.exists(metadata_path):
        raise ValueError(f"{api.KERNEL_METADATA_FILE} was not created by kernels_initialize.")

    with open(metadata_path, encoding="utf-8") as file:
        metadata = json.load(file) or {}

    metadata["id"] = f"{get_authenticated_username(api)}/{slugify_kernel_title(normalized_title)}"
    metadata.pop("id_no", None)
    metadata["title"] = normalized_title
    metadata["code_file"] = code_file
    metadata["language"] = "python"
    metadata["kernel_type"] = "script"
    metadata["is_private"] = bool(is_private)
    metadata["enable_gpu"] = False
    metadata["enable_tpu"] = False
    metadata["enable_internet"] = bool(enable_internet)
    metadata["keywords"] = metadata.get("keywords") or []
    metadata["dataset_sources"] = metadata.get("dataset_sources") or []
    metadata["competition_sources"] = metadata.get("competition_sources") or []
    metadata["kernel_sources"] = metadata.get("kernel_sources") or []
    metadata["model_sources"] = metadata.get("model_sources") or []
    metadata["docker_image"] = metadata.get("docker_image") or ""
    metadata["machine_shape"] = metadata.get("machine_shape") or "None"
    return metadata
