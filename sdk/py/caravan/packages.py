from enum import Enum
from importlib import resources
from typing import TYPE_CHECKING

from ape.contracts import ContractContainer
from ethpm_types import PackageManifest
from packaging.version import Version

if TYPE_CHECKING:
    from ape.api import ReceiptAPI

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
    SINGLETON = "Caravan"
    PROXY = "CaravanProxy"
    FACTORY = "CaravanFactory"

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

    def deploy(
        self, version: Version | str = STABLE_VERSION, **txn_args
    ) -> "ReceiptAPI":
        from createx.main import CreateX

        try:
            createx = CreateX()
        except RuntimeError:
            createx = CreateX.inject()

        Type = self(version=version)

        match self:
            case PackageType.SINGLETON:
                call_args = [str(version)]
                salt = f"{__package__}:{Type.name} v{version}"

            case PackageType.FACTORY:
                proxy_initcode = (
                    PackageType.PROXY().contract_type.get_deployment_bytecode()
                )
                call_args = [proxy_initcode]
                # NOTE: The factory should never change between versions
                salt = f"{__package__}:{Type.name}"

            case _:
                raise RuntimeError(f"Do not deploy {self.name} directly!")

        return createx.deploy(
            Type,
            *call_args,
            salt=salt,
            # NOTE: We want anyone to deploy this on the same address on any chain
            sender_protection=False,
            redeploy_protection=False,
            **txn_args,
        )
