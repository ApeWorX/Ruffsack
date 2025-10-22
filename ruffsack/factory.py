from typing import TYPE_CHECKING

from ape.types import AddressType
from ape.utils import ManagerAccessMixin, cached_property
from packaging.version import Version

from .main import Ruffsack
from .packages import MANIFESTS, PackageType

if TYPE_CHECKING:
    from ape.contracts import ContractInstance


class Factory(ManagerAccessMixin):
    def __init__(self, address: AddressType | None = None):
        if address:
            self.address = address

        else:
            # TODO: Refactor to use deterministic deployment address
            self.address = self.local_project.RuffsackFactory.deployments[0].address

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
            for log in self.contract.NewRelease.range(
                self._last_cached, latest_block + 1
            ):
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
        tag: str | None = None,
        **txn_args,
    ) -> Ruffsack:
        if threshold is None:
            threshold = len(signers) // 2

        if isinstance(version, str):
            version = Version(version)

        args = [signers, threshold]
        if tag is not None:
            args.extend([str(version) if version else "stable", tag])

        elif version is not None:
            args.append(str(version))

        if version is None:
            version = Version(self.contract.last_release())

        receipt = self.contract.new(*args, **txn_args)

        return Ruffsack(
            address=receipt.events[0].new_sack, version=version, factory=self
        )
