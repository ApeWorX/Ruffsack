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

from .main import Ruffsack


if TYPE_CHECKING:
    from collections.abc import Callable

    from ape.api import AccountAPI, NetworkAPI


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


def propose_from_simulation():
    def inner(cmd: "Callable"):
        parameters = list(inspect.signature(cmd).parameters)

        @click.command(cls=ConnectedProviderCommand)
        @ape_cli_context()
        @account_option(
            "--proposer",
            prompt="Account to propose or submit transaction with",
        )
        @click.option(
            "--parent",
            type=HexBytes,
            default=None,
            help="Msghash to use as parent (defaults to `head`)",
        )
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
