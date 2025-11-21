from typing import TYPE_CHECKING

from ape.types import AddressType
from ape.utils import ManagerAccessMixin, cached_property
from packaging.version import Version

from .main import Ruffsack
from .packages import STABLE_VERSION, PackageType

if TYPE_CHECKING:
    from ape.contracts import ContractInstance


class Factory(ManagerAccessMixin):
    def __init__(self, address: AddressType | None = None):
        if address:
            self.address = address

        elif len((factory_type := PackageType.FACTORY()).deployments) == 0:
            raise RuntimeError("No RuffsackFactory deployment on this chain")

        else:
            # NOTE: Override cached value of `contract`
            self.contract = factory_type.deployments[0]
            self.address = self.contract.address

        # NOTE: also lets us override for testing
        self._cached_releases: dict[Version, "ContractInstance"] = dict()

    # TODO: classmethod `.inject`?

    @cached_property
    def contract(self) -> "ContractInstance":
        return PackageType.FACTORY().at(
            self.address,
            fetch_from_explorer=False,
            detect_proxy=False,
        )

    def get_release(self, version: Version) -> "ContractInstance | None":
        if release := self._cached_releases.get(version):
            return release

        elif not (singleton_type := PackageType.SINGLETON(version)).deployments:
            return None

        elif not (release := singleton_type.deployments[-1]).code:
            return None

        self._cached_releases[version] = release
        return release

    def new(
        self,
        signers: list[AddressType],
        threshold: int | None = None,
        version: Version | str = STABLE_VERSION,
        tag: str | None = None,
        **txn_args,
    ) -> Ruffsack:
        if threshold is None:
            threshold = len(signers) // 2

        if isinstance(version, str):
            version = Version(version.lstrip("v"))

        release = self.get_release(version)

        args = [release, signers, threshold]
        if tag is not None:
            args.append(tag)

        receipt = self.contract.new(*args, **txn_args)

        return Ruffsack(
            address=receipt.events[0].new_sack, version=version, factory=self
        )
