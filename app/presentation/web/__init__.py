# Web routes (server-rendered)


"""Web presentation package."""

from app.presentation.web import (
    auth,
    files,
    workspace,
    converter,
    intelligence,
    admin,
)

# Export helper functions from files module
from app.presentation.web.files import file_to_dict, files_to_dict_list

__all__ = [
    "auth",
    "files",
    "workspace",
    "converter",
    "intelligence",
    "admin",
    "file_to_dict",
    "files_to_dict_list",
]
