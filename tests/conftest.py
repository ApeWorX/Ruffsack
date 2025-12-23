from typing import TYPE_CHECKING

import pytest
from packaging.version import Version
from ruffsack import Factory
from ruffsack.packages import MANIFESTS, PackageType
from ruffsack.queue import QueueManager

if TYPE_CHECKING:
    from ape.api import AccountAPI
    from ape.contracts import ContractInstance


@pytest.fixture(scope="session", params=list(f"v{v}" for v in MANIFESTS))
def VERSION(request):
    return Version(request.param.lstrip("v"))


@pytest.fixture(scope="session")
def deployer(accounts):
    return accounts[-1]


@pytest.fixture(scope="session")
def factory(project, deployer):
    proxy_initcode = project.RuffsackProxy.contract_type.get_deployment_bytecode()
    return Factory(deployer.deploy(project.RuffsackFactory, proxy_initcode).address)


@pytest.fixture(
    scope="session",
    params=["1/1", "1/2", "2/3", "2/4", "3/5"],
)
def WALLET_PARAMS(request):
    THRESHOLD, NUM_OWNERS = request.param.split("/")
    return int(THRESHOLD), int(NUM_OWNERS)


@pytest.fixture(scope="session")
def owners(accounts, WALLET_PARAMS):
    _, NUM_OWNERS = WALLET_PARAMS
    return accounts[:NUM_OWNERS]


@pytest.fixture(scope="session")
def THRESHOLD(WALLET_PARAMS):
    THRESHOLD, _ = WALLET_PARAMS
    return THRESHOLD


@pytest.fixture(scope="session")
def create_release(VERSION, deployer, factory):
    def create_release(
        version: Version | None = None,
        creator: "AccountAPI | None" = None,
    ) -> "ContractInstance":
        singleton = (creator or deployer).deploy(
            PackageType.SINGLETON(VERSION),
            str(version or VERSION),  # Allows over-writing version
        )
        factory._cached_releases[version or VERSION] = singleton
        return singleton

    return create_release


@pytest.fixture(scope="session")
def singleton(VERSION, factory, create_release):
    if singleton := factory.get_release(VERSION):
        return singleton

    return create_release()


@pytest.fixture(scope="session")
def new_sack(deployer, factory, create_release):
    def new_sack(
        owners: list["AccountAPI"],
        threshold: int,
        version: Version | None = None,
        **txn_args,
    ) -> "ContractInstance":
        if not factory.get_release(version):
            create_release(version, deployer)

        sack = factory.new(owners, threshold, version=version, **txn_args)
        # NOTE: Make sure to use empty queue for testing
        sack.queue = QueueManager()
        return sack

    return new_sack


@pytest.fixture(scope="session")
def sack(VERSION, owners, THRESHOLD, new_sack):
    return new_sack(owners, THRESHOLD, version=VERSION, sender=owners[0])
