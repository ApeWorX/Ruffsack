from enum import Enum
from importlib import resources

from ape.contracts import ContractContainer
from ethpm_types import PackageManifest
from packaging.version import Version

MANIFESTS = {
    Version(
        manifest.name.removesuffix(".json").lstrip("v")
    ): PackageManifest.model_validate_json(manifest.read_text())
    for manifest in resources.files(__package__).joinpath("manifests").iterdir()
    if manifest.name.endswith(".json")
}

NEXT_VERSION = max(MANIFESTS)
try:
    STABLE_VERSION = sorted(MANIFESTS)[-2]

except IndexError:
    # TODO: Remove once more than one version exists
    STABLE_VERSION = NEXT_VERSION


class PackageType(str, Enum):
    SINGLETON = "Ruffsack"
    PROXY = "RuffsackProxy"
    FACTORY = "RuffsackFactory"

    def __call__(self, version: Version | str = STABLE_VERSION) -> "ContractContainer":
        if not isinstance(version, Version):
            version = Version(version.lstrip("v"))

        if not (package := MANIFESTS.get(version)):
            available_versions = ", ".join(f"v{v}" for v in MANIFESTS)
            raise ValueError(
                f"Unknown package version v{version}, should be one of: {available_versions}"
            )

        elif not (contract_type := package.get_contract_type(self.value)):
            raise ValueError(f"Unknown type in package v{version}: {self.value}")

        return ContractContainer(contract_type)
