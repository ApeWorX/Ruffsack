import math
from typing import TYPE_CHECKING, Any

import click
from ape import project
from ape.cli import ConnectedProviderCommand, account_option
from ape.types import AddressType
from ape.utils import ZERO_ADDRESS
from createx import CreateX
from packaging.version import Version

from ruffsack import Factory
from ruffsack.packages import MANIFESTS

if TYPE_CHECKING:
    from ape.api.accounts import AccountAPI


def version_option():
    def _convert_version(ctx, _param, value):
        try:
            return Version(value)

        except ValueError as e:
            raise click.UsageError(
                ctx=ctx,
                message=f"'{value}' is not a valid verison identifier.",
            ) from e

    return click.option(
        "--version",
        type=click.Choice(list(str(v) for v in MANIFESTS)),
        default=str(max(MANIFESTS)),
        callback=_convert_version,
        help="Version to use when deploying the contract. Defaults to latest in SDK.",
    )


@click.group()
def cli():
    """Manage Ruffsack wallets (https://ruffsack.xyz)"""


@cli.command(cls=ConnectedProviderCommand)
@account_option()
@version_option()
@click.option(
    "--threshold",
    type=int,
    default=0,
    help="The value to use for the wallet's threshold. "
    "Defaults to half the number of signers (rounding up)",
)
@click.option("--tag", default=None)
@click.argument("signers", nargs=-1)
def new(version, threshold, tag, signers, account):
    """Create a new Ruffsack multisig wallet on the given network"""
    from ape import accounts, convert

    signers = [
        accounts.load(s) if s in accounts.aliases else convert(s, AddressType)
        for s in signers
    ]

    if len(signers) == 0:
        raise click.UsageError("Must provider at least one signer")

    elif len(signers) > 11:
        raise click.UsageError("Cannot use Ruffsack with more than 11 signers")

    if not threshold:
        threshold = math.ceil(len(signers) / 2)

    elif 0 > threshold or threshold > len(signers):
        raise click.UsageError("Cannot use a value higher than number of signers")

    factory = Factory()
    sack = factory.new(
        signers,
        threshold=threshold,
        version=version,
        tag=tag,
        sender=account,
    )
    click.secho(f"New Ruffsack deployed: {sack.address}", fg="yellow")


@cli.group()
def sudo():
    """Manage the Ruffsack system contracts [ADVANCED]"""


@sudo.group()
def deploy():
    """
    Deploy the Ruffsack system contracts

    NOTE: **Anyone can deploy these** (if CreateX is supported)
    """


@deploy.command(cls=ConnectedProviderCommand)
@account_option()
@click.argument("governance", default=None, required=False)
def factory(account: "AccountAPI", governance: Any):
    """Deploy Proxy Factory to the specified network"""

    proxy_initcode = project.RuffsackProxy.contract_type.get_deployment_bytecode()

    try:
        createx = CreateX()
    except RuntimeError:
        createx = CreateX.inject()

    factory = createx.deploy(
        project.RuffsackFactory,
        governance or account,
        proxy_initcode,
        sender=account,
        sender_protection=False,
        redeploy_protection=False,
        salt="Ruffsack Factory",
    )
    click.secho(f"Factory deployed to {factory.address}", fg="green")


@deploy.command(cls=ConnectedProviderCommand)
@version_option()
@account_option()
def singleton(version: Version, account: "AccountAPI"):
    """Deploy the given version of singleton contract"""

    try:
        createx = CreateX()
    except RuntimeError:
        createx = CreateX.inject()

    singleton = createx.deploy(
        MANIFESTS[version].Ruffsack,
        str(version),
        sender=account,
        sender_protection=False,
        redeploy_protection=False,
        salt=f"Ruffsack v{version}",
    )
    click.secho(f"Single {version} deployed to {singleton.address}", fg="green")


@sudo.command(cls=ConnectedProviderCommand)
@version_option()
@account_option()
def release(version: Version, account: "AccountAPI"):
    """Add a new release to the Factory"""

    manifest = MANIFESTS[version]

    if len(manifest.Ruffsack.deployments) == 0:
        raise click.UsageError("Cannot autodetect last release of Singleton")

    release = manifest.Ruffsack.deployments[-1]

    if len(manifest.RuffsackFactory.deployments) == 0:
        raise click.UsageError("Cannot autodetect Factory to link Singleton")

    elif (factory := manifest.RuffsackFactory.deployments[-1]).governance() != account:
        raise click.UsageError(
            "Cannot link Singleton without governance account access"
        )

    elif factory.releases(release.VERSION()) != ZERO_ADDRESS:
        raise click.UsageError("Release process will fail. Release already set.")

    factory.add_release(release, sender=account)
