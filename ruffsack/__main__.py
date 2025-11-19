import math
from typing import TYPE_CHECKING
import runpy

from ape.exceptions import ConversionError
import click
from ape.cli import ConnectedProviderCommand, account_option
from ape.cli import ape_cli_context
from ape.types import AddressType
from createx import CreateX
from packaging.version import Version

from .cli import ruffsack_argument
from .factory import Factory
from .packages import MANIFESTS, PackageType, NEXT_VERSION

if TYPE_CHECKING:
    from ape.api.accounts import AccountAPI
    from ape.contracts import ContractInstance

    from .main import Ruffsack


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
def config():
    """Commands to modify on-chain configuration"""


@config.command(cls=ConnectedProviderCommand)
@version_option()
@account_option("--submitter")
@ruffsack_argument()
def migrate(version: Version, submitter: "AccountAPI", ruffsack: "Ruffsack"):
    """Migrate the version of your Ruffsack"""

    if (current_version := ruffsack.version) == version:
        raise click.UsageError("Cannot migrate to the same version")

    if click.confirm(f"Migrate from {current_version} to {version}?"):
        ruffsack.migrate(new_version=version, submitter=submitter)


@config.command(cls=ConnectedProviderCommand)
@click.option(
    "--add",
    "signers_to_add",
    multiple=True,
    callback=_get_accounts,
    help="Add signers to Ruffsack",
)
@click.option(
    "--remove",
    "signers_to_remove",
    multiple=True,
    callback=_get_accounts,
    help="Remove signers from Ruffsack",
)
@click.option("--threshold", type=int, default=None, help="Change signing threshold")
@account_option("--submitter")
@ruffsack_argument()
def signers(
    signers_to_add: list[str],
    signers_to_remove: list[str],
    threshold: int | None,
    submitter: "AccountAPI",
    ruffsack: "Ruffsack",
):
    """Rotate signers and/or change signer threshold"""

    if not signers_to_add and not signers_to_remove and not threshold:
        raise click.UsageError("No modifications detected")

    click.echo("Current signers:\n- " + "\n- ".join(ruffsack.signers))

    if signers_to_remove:
        click.echo("Remove:\n- " + "\n- ".join(signers_to_remove))

    if signers_to_add:
        click.echo("Add:\n- " + "\n- ".join(signers_to_add))

    if threshold:
        click.echo(f"Modify threshold from {ruffsack.threshold} to {threshold}")

    if click.confirm("Proceed?"):
        ruffsack.rotate_signers(
            signers_to_add=signers_to_add,
            signers_to_remove=signers_to_remove,
            threshold=threshold,
            submitter=submitter,
        )


@config.group()
def admin_guard():
    """View and configure the Admin Guard in a Ruffsack"""


@admin_guard.command(name="view", cls=ConnectedProviderCommand)
@ruffsack_argument()
def view_admin_guard(ruffsack: "Ruffsack"):
    """Show Admin Guard in Ruffsack (if any)"""

    if admin_guard := ruffsack.admin_guard:
        click.echo(str(admin_guard))


@config.group()
def execute_guard():
    """View and configure the Execute Guard in a Ruffsack"""


@execute_guard.command(name="view", cls=ConnectedProviderCommand)
@ruffsack_argument()
def view_execute_guard(ruffsack: "Ruffsack"):
    """Show Execute Guard in Ruffsack (if any)"""

    if execute_guard := ruffsack.execute_guard:
        click.echo(str(execute_guard))


@config.group()
def modules():
    """View and configure the Modules in a Ruffsack"""


@modules.command(name="list", cls=ConnectedProviderCommand)
@ruffsack_argument()
def list_modules(ruffsack: "Ruffsack"):
    """List Modules in Ruffsack (if any)"""

    for module in ruffsack.modules:
        click.echo(str(module))


@modules.command(name="enable", cls=ConnectedProviderCommand)
@account_option("--submitter")
@ruffsack_argument()
@click.argument("module")
def enable_module(
    submitter: "AccountAPI", ruffsack: "Ruffsack", module: "ContractInstance"
):
    """Enable Module in Ruffsack"""

    if module in ruffsack.modules:
        raise click.UsageError(f"Module {module} already enabled")

    elif click.confirm(f"Enable module {module}?"):
        ruffsack.modules.enable(module, submitter=submitter)


@modules.command(name="disable", cls=ConnectedProviderCommand)
@account_option("--submitter")
@ruffsack_argument()
@click.argument("module")
def disable_module(
    submitter: "AccountAPI", ruffsack: "Ruffsack", module: "ContractInstance"
):
    """Disable Module in Ruffsack"""

    if module not in ruffsack.modules:
        raise click.UsageError(f"Module {module} is not enabled")

    elif click.confirm(f"Disable module {module}?"):
        ruffsack.modules.disable(module, submitter=submitter)


@cli.group()
def queue():
    """Commands to manage off-chain queue"""


@queue.command(cls=ConnectedProviderCommand)
@ape_cli_context()
@account_option("--proposer")
@click.option("--submit", is_flag=True, default=False)
@click.option("--stop-at", default=None)
@ruffsack_argument()
def run(cli_ctx, network, proposer, submit, stop_at, ruffsack):
    """
    Run scripts in the local Ruffsack queue to create a new head

    This command uses scripts from `scripts/q*.py` and "replays" them from the Ruffsack's current
    on-chain head, up to the last script found in the folder or until the new head is `--stop-at`.
    When executed using a fork network, it will only perform a simulated validation of the script.
    When executed using a live network, it will publish the transaction ONLY IF the transaction at
    that msghash does not exist in the off-chain queue.

    To enable this, scripts under `scripts/` must be properly named, and all use
    `ruffsack.cli.propose_from_simulation`.
    """

    if not (
        available_queue_scripts := {
            script.stem[1:]: script.relative_to(cli_ctx.local_project.path)
            for script in cli_ctx.local_project.scripts_folder.glob("q*.py")
        }
    ):
        raise click.UsageError("No scripts to queue detected in 'scripts/'.")

    elif (len(hashlen_sizes := set(len(s) for s in available_queue_scripts))) > 1:
        raise click.UsageError("All hashes in script filenames must be same length")

    # NOTE: Only one option, so pop it
    hashlen = hashlen_sizes.pop()
    assert stop_at is None or len(stop_at) == hashlen, (
        f"Does not match hash length of {hashlen}: '{stop_at}'"
    )

    parent = ruffsack.head
    cli_ctx.logger.info(f"Current head: {parent.to_0x_hex()}")

    while available_queue_scripts and parent.hex()[:hashlen] != stop_at:
        if not (script := available_queue_scripts.pop(parent.hex()[:hashlen], None)):
            break

        if not (cmd := runpy.run_path(str(script), run_name=script.stem).get("cli")):
            raise click.UsageError(f"No command `cli` detected in {script}.")

        cli_ctx.logger.info(f"Running '{script}':\n\n  {cmd.help}\n")
        # NOTE: This matches signature from `ruffsack.cli:propose_from_simulation`
        parent = cmd.callback.__wrapped__(
            cli_ctx, network, proposer, parent, submit, ruffsack
        )

        cli_ctx.logger.success(f"New head set: {parent.to_0x_hex()}")

    cli_ctx.logger.success(f"Queue for '{ruffsack.address}' up-to-date!")


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
