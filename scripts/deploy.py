import click
from ape import project
from ape.cli import ConnectedProviderCommand, account_option
from ruffsack.packages import MANIFESTS


@click.group()
def cli():
    """Deploy the Ruffsack system contracts"""


@cli.command(cls=ConnectedProviderCommand)
@account_option()
@click.argument("governance", default=None, required=False)
def factory(account, governance):
    """Deploy Proxy Factory to the specified network"""

    proxy_initcode = project.RuffsackProxy.contract_type.get_deployment_bytecode()
    account.deploy(project.RuffsackFactory, governance or account, proxy_initcode)
    # TODO: Adapt to use https://ercs.ethereum.org/ERCS/erc-7955?


@cli.command(cls=ConnectedProviderCommand)
@click.option(
    "--version",
    default=str(max(MANIFESTS)),
    help="Version to use when deploying the contract. Defaults to latest in SDK.",
)
@account_option()
def singleton(version, account):
    """Deploy the given version of singleton contract"""

    account.deploy(project.Ruffsack, version)
