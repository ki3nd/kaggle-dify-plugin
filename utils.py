from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator


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
