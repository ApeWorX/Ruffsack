from typing import TYPE_CHECKING

from ape.types import AddressType
from ape.utils import ManagerAccessMixin, cached_property
from packaging.version import Version

from .packages import MANIFESTS, PackageType

if TYPE_CHECKING:
    from ape.contracts import ContractInstance


class Factory(ManagerAccessMixin):
    def __init__(self, address: AddressType | None = None):
        # TODO: Refactor to use deterministic deployment address
        self.address = address or self.local_project.RuffsackFactory.deployments[0]
        self._cached_releases: dict[Version, "ContractInstance"] = dict()
        self._last_cached: int = 0

    # TODO: classmethod `.inject`?

    @cached_property
    def contract(self) -> "ContractInstance":
        return self.chain_manager.contracts.instance_at(
            self.address,
            contract_type=PackageType.FACTORY(max(MANIFESTS)),
        )

    @property
    def releases(self) -> dict[Version, "ContractInstance"]:
        if (latest_block := self.chain_manager.blocks.head.number) > self._last_cached:
            for log in self.contract.NewRelease.range(self._last_cached, latest_block):
                self._cached_releases[Version(log.version)] = (
                    self.chain_manager.contracts.instance_at(
                        log.implementation,
                        contract_type=PackageType.SINGLETON(log.version),
                    )
                )

        self._last_cached = latest_block
        return self._cached_releases

    def new(
        self,
        signers: list[AddressType],
        threshold: int | None = None,
        version: Version | str | None = None,
        salt: str | bytes | None = None,
        **txn_args,
    ) -> "ContractInstance":
        if threshold is None:
            threshold = len(signers) // 2

        if isinstance(version, str):
            version = Version(version)

        if salt is not None:
            if version is None:
                version = Version(self.contract.last_version())

            receipt = self.contract.new(
                signers,
                threshold,
                str(version),
                salt,
                **txn_args,
            )

        elif version is not None:
            receipt = self.contract.new(
                signers,
                threshold,
                str(version),
                **txn_args,
            )

        else:
            receipt = self.contract.new(
                signers,
                threshold,
                **txn_args,
            )
            version = Version(self.contract.last_version())

        new_ruffsack_address = receipt.events[0].new_sack
        return self.chain_manager.contracts.instance_at(
            new_ruffsack_address,
            contract_type=PackageType.SINGLETON(version),
        )
