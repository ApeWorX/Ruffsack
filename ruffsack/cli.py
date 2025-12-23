import inspect
from typing import TYPE_CHECKING

import click
from ape.cli import (
    ApeCliContextObject,
    ConnectedProviderCommand,
    account_option,
    ape_cli_context,
)
from ape.exceptions import ConversionError
from ape.types import AddressType, HexBytes
from packaging.version import Version

from .main import Ruffsack
from .packages import MANIFESTS, NEXT_VERSION


if TYPE_CHECKING:
    from collections.abc import Callable

    from ape.api import AccountAPI, NetworkAPI


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


def ruffsack_argument():
    def ruffsack_callback(ctx, param, value):
        from ape import accounts, convert

        if value in accounts.aliases:
            if not isinstance(account := accounts.load(value), Ruffsack):
                raise click.BadParameter(
                    ctx=ctx,
                    param=param,
                    message=f"Alias {value} is not a Ruffsack wallet.",
                )

            return account

        try:
            address = convert(value, AddressType)

        except ConversionError as e:
            raise click.BadParameter(
                ctx=ctx,
                param=param,
                message=f"Value '{value}' is not convertible to an address",
            ) from e

        return Ruffsack(address)

    return click.argument("ruffsack", type=AddressType, callback=ruffsack_callback)


def parent_option():
    def parse_hex(ctx, param, value):
        if value is None:
            return value

        try:
            value = HexBytes(value)

        except ValueError as e:
            raise click.BadOptionUsage(
                message=f"Value '{value}' is not hex-encoded bytes",
                option_name=param,
                ctx=ctx,
            ) from e

        else:
            if (actual_length := len(value)) != 32:
                raise click.BadOptionUsage(
                    message=f"Value '{value}' must be length 32, not {actual_length}",
                    option_name=param,
                    ctx=ctx,
                )
            return value

    return click.option(
        "--parent",
        default=None,
        callback=parse_hex,
        help="Msghash to use as parent for operation (defaults to on-chain `head`)",
    )


def propose_from_simulation():
    def inner(cmd: "Callable"):
        parameters = list(inspect.signature(cmd).parameters)

        @click.command(cls=ConnectedProviderCommand)
        @ape_cli_context()
        @account_option(
            "--proposer",
            prompt="Account to propose or submit transaction with",
        )
        @parent_option()
        @click.option(
            "--submit",
            is_flag=True,
            default=False,
            help="Submit the transaction",
        )
        @ruffsack_argument()
        def cli(
            cli_ctx: ApeCliContextObject,
            network: "NetworkAPI",
            proposer: "AccountAPI",
            parent: HexBytes | None,
            submit: bool,
            ruffsack: "Ruffsack",
        ) -> HexBytes:
            if network.is_local and parent is not None:
                ruffsack.set_head(parent)

            batch = ruffsack.new_batch(parent=parent)

            with batch.add_from_simulation() as sack_account:
                args: list = list()
                if len(parameters) >= 1:
                    args.append(sack_account)
                if len(parameters) >= 2:
                    args.append(proposer)

                cmd(*args)

            cli_ctx.logger.info(f"Found {len(batch.calls)} calls in simulation")

            batch(submit=submit, sender=proposer)

            # NOTE: So our `ruffsack queue commit` command can get the latest hash if not committed
            return batch.hash

        cli.help = cmd.__doc__
        return cli

    return inner
