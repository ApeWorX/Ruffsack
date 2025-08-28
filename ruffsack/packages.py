from enum import Enum
from importlib import resources
from typing import TYPE_CHECKING

from ethpm_types import PackageManifest
from packaging.version import Version

if TYPE_CHECKING:
    from ape.contracts import ContractContainer

MANIFESTS = {
    Version(
        manifest.name.removesuffix(".json").lstrip("v")
    ): PackageManifest.model_validate_json(manifest.read_text())
    for manifest in resources.files(__package__).joinpath("manifests").iterdir()
    if manifest.name.endswith(".json")
}


class PackageType(str, Enum):
    SINGLETON = "Ruffsack"
    PROXY = "RuffsackProxy"
    FACTORY = "RuffsackFactory"

    def __call__(self, version: Version | str) -> "ContractContainer":
        if not isinstance(version, Version):
            version = Version(version.lstrip("v"))

        if not (package := MANIFESTS.get(version)):
            available_versions = ", ".join(f"v{v}" for v in MANIFESTS)
            raise ValueError(
                f"Unknown package version v{version}, should be one of: {available_versions}"
            )

        elif not (contract_type := package.get_contract_type(self.value)):
            raise ValueError(f"Unknown type in package v{version}: {self.value}")

        return contract_type
