from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from utils import build_authenticated_kaggle_api


class KaggleProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            token = (credentials.get("api_token") or "").strip()
            api = build_authenticated_kaggle_api(token)
            # Verify token by making a simple authenticated call.
            api.kernels_list(page=1, page_size=1, mine=True)
        except SystemExit as e:
            raise ToolProviderCredentialValidationError("Kaggle authentication failed.") from e
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
