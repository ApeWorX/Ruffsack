import click
from ape import project
from ape.cli import ConnectedProviderCommand, account_option
from ape.utils import ZERO_ADDRESS


@click.command(cls=ConnectedProviderCommand)
@account_option()
def cli(account):
    """Create a new release in the Factory"""

    if len(project.Ruffsack.deployments) == 0:
        raise click.UsageError("Cannot autodetect last release of Singleton")

    release = project.Ruffsack.deployments[-1]

    if len(project.RuffsackFactory.deployments) == 0:
        raise click.UsageError("Cannot autodetect Factory to link Singleton")

    elif (factory := project.RuffsackFactory.deployments[-1]).governance() != account:
        raise click.UsageError(
            "Cannot link Singleton without governance account access"
        )

    elif factory.releases(release.VERSION()) != ZERO_ADDRESS:
        raise click.UsageError("Release process will fail. Release already set.")

    if click.confirm(f"Set 'v{release.VERSION()}' to {release.address}?"):
        factory.add_release(release, sender=account)
