from typing import TYPE_CHECKING

import pytest
from packaging.version import Version
from ruffsack import Factory
from ruffsack.packages import MANIFESTS, PackageType

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
def governance(accounts):
    return accounts[-2]


@pytest.fixture(scope="session")
def factory(project, deployer, governance):
    proxy_initcode = project.RuffsackProxy.contract_type.get_deployment_bytecode()
    return Factory(
        deployer.deploy(project.RuffsackFactory, governance, proxy_initcode).address
    )


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
def create_release(VERSION, deployer, governance, factory):
    def create_release(
        version: Version | None = None,
        creator: "AccountAPI | None" = None,
    ) -> "ContractInstance":
        singleton = (creator or deployer).deploy(
            PackageType.SINGLETON(VERSION),
            str(version or VERSION),  # Allows over-writing version
        )

        factory.contract.add_release(singleton, sender=governance)
        return singleton

    return create_release


@pytest.fixture(scope="session")
def singleton(VERSION, deployer, factory, create_release):
    if singleton := factory.releases.get(VERSION):
        return singleton

    return create_release(VERSION, deployer)


@pytest.fixture(scope="session")
def new_sack(deployer, factory, create_release):
    def new_sack(
        owners: list["AccountAPI"],
        threshold: int,
        version: Version | None = None,
        **txn_args,
    ) -> "ContractInstance":
        if version and version not in factory.releases:
            create_release(version, deployer)

        return factory.new(owners, threshold, version=version, **txn_args)

    return new_sack


@pytest.fixture(scope="session")
def sack(VERSION, owners, THRESHOLD, new_sack):
    return new_sack(owners, THRESHOLD, version=VERSION, sender=owners[0])


@pytest.fixture(params=["onchain", "offchain"])
def approval_flow(request):
    return request.param
