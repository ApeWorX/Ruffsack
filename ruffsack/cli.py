import click
from ape.exceptions import ConversionError
from ape.types import AddressType

from .main import Ruffsack


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
