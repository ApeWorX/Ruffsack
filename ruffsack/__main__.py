import math

import click
from ape.cli import ConnectedProviderCommand, account_option
from ape.types import AddressType

from ruffsack import Factory
from ruffsack.packages import MANIFESTS


@click.group()
def cli():
    """Manage Ruffsack wallets (https://ruffsack.xyz)"""


@cli.command(cls=ConnectedProviderCommand)
@account_option()
@click.option(
    "--version",
    default=str(max(MANIFESTS)),
    help="Version to use when creating the multisig. Defaults to latest in SDK.",
)
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
