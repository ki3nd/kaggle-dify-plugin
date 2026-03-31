from collections.abc import Generator
import json
import os
import tempfile
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils import build_authenticated_kaggle_api


class KaggleGetKernelMetadataTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        kernel_id = str(tool_parameters.get("kernel_id", "")).strip()
        if not kernel_id:
            raise ValueError("kernel_id is required.")
        if "/" not in kernel_id:
            raise ValueError("kernel_id must be in the format 'owner/kernel-slug'.")

        owner_slug, kernel_slug = kernel_id.split("/", 1)
        api = build_authenticated_kaggle_api(str(self.runtime.credentials.get("api_token", "")).strip())
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

        temp_root = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_root, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="kaggle-kernel-metadata-", dir=temp_root) as temp_dir:
            with api.build_kaggle_client() as kaggle:
                request = ApiGetKernelRequest()
                request.user_name = owner_slug
                request.kernel_slug = kernel_slug
                response = kaggle.kernels.kernels_api_client.get_kernel(request)

            server_metadata = response.metadata
            language = str(response.blob.language).lower()
            kernel_type = str(response.blob.kernel_type).lower()
            if kernel_type == "notebook":
                code_file = f"{response.blob.slug}.ipynb" if language == "python" else f"{response.blob.slug}"
            else:
                code_file = f"{response.blob.slug}.py" if language == "python" else f"{response.blob.slug}"

            metadata = {
                "id": server_metadata.ref,
                "id_no": server_metadata.id,
                "title": server_metadata.title,
                "code_file": code_file,
                "language": server_metadata.language,
                "kernel_type": server_metadata.kernel_type,
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

            metadata_path = os.path.join(temp_dir, api.KERNEL_METADATA_FILE)
            with open(metadata_path, "w", encoding="utf-8") as file:
                json.dump(metadata, file, indent=2)

        yield self.create_json_message(metadata)
