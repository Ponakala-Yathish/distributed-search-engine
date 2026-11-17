"""FastAPI service for serving exported distributed-search indexes."""

from typing import Any

__all__ = ["create_app"]


def create_app(*args: Any, **kwargs: Any) -> Any:
    from .main import create_app as application_factory

    return application_factory(*args, **kwargs)
