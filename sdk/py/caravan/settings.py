import os
from pathlib import Path


USER_CACHE_DIR: Path = (
    path
    if (
        (value := os.environ.get("XDG_CACHE_HOME"))
        and (path := Path(value)).exists()
        and path.is_absolute()
    )
    else (Path.home() / ".cache")
) / "caravan"
USER_CACHE_DIR.mkdir(exist_ok=True)

USER_CONFIG_DIR: Path = (
    path
    if (
        (value := os.environ.get("XDG_CONFIG_HOME"))
        and (path := Path(value)).exists()
        and path.is_absolute()
    )
    else (Path.home() / ".config")
) / "caravan"
USER_CONFIG_DIR.mkdir(exist_ok=True)
