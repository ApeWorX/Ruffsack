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
) / "ruffsack"
USER_CACHE_DIR.mkdir(exist_ok=True)

USER_CONFIG_DIR: Path = (
    path
    if (
        (value := os.environ.get("XDG_CONFIG_HOME"))
        and (path := Path(value)).exists()
        and path.is_absolute()
    )
    else (Path.home() / ".config")
) / "ruffsack"
USER_CONFIG_DIR.mkdir(exist_ok=True)
