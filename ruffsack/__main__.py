import math
from typing import TYPE_CHECKING

from ape.exceptions import ConversionError
import click
from ape.cli import ConnectedProviderCommand, account_option
from ape.types import AddressType
from createx import CreateX
from packaging.version import Version

from ruffsack import Factory
from ruffsack.packages import MANIFESTS
from ruffsack.packages import PackageType, NEXT_VERSION

if TYPE_CHECKING:
    from ape.api.accounts import AccountAPI


def version_option():
    def _convert_version(ctx, _param, value):
        if value is None:
            # NOTE: Temporary until v1 is released
            version = NEXT_VERSION

        else:
            try:
                version = Version(value)

            except ValueError as e:
                raise click.UsageError(
                    ctx=ctx,
                    message=f"'{value}' is not a valid verison identifier.",
                ) from e

        if version == NEXT_VERSION:
            click.echo(
                click.style("WARNING:", fg="yellow")
                + f"  Using un-released version {version}"
            )

        return version

    released_versions = list(str(v) for v in MANIFESTS if v != NEXT_VERSION)
    default_version = str(max(released_versions)) if released_versions else None
    return click.option(
        "--version",
        type=click.Choice([*released_versions, str(NEXT_VERSION)]),
        default=default_version,
        callback=_convert_version,
        help="Version to use when deploying the contract. Defaults to last stable release.",
    )


@click.group()
def cli():
    """Manage Ruffsack wallets (https://ruffsack.xyz)"""


def _get_accounts(ctx, param, values):
    from ape import accounts, convert

    def get_account(value):
        if value in accounts.aliases:
            return accounts.load(value)

        elif value.startswith("TEST::"):
            return accounts.test_accounts[int(value[6:])]

        try:
            return convert(value, AddressType)

        except ConversionError as e:
            raise click.UsageError(
                ctx=ctx,
                message=f"Not a valid '{param}': {value}",
            ) from e

    return [get_account(v) for v in values]


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
@click.argument("signers", nargs=-1, callback=_get_accounts)
def new(version, threshold, tag, signers, account):
    """Create a new Ruffsack multisig wallet on the given network"""

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
def factory(account: "AccountAPI"):
    """Deploy Proxy Factory to the specified network"""

    proxy_initcode = PackageType.PROXY().contract_type.get_deployment_bytecode()

    try:
        createx = CreateX()
    except RuntimeError:
        createx = CreateX.inject()

    factory = createx.deploy(
        PackageType.FACTORY(),
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
        PackageType.SINGLETON(version),
        str(version),
        sender=account,
        sender_protection=False,
        redeploy_protection=False,
        salt=f"Ruffsack v{version}",
    )
    click.secho(f"Ruffsack v{version} deployed to {singleton.address}", fg="green")
