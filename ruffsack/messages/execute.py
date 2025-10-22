from typing import TYPE_CHECKING, Self

from ape.types import HexBytes
from ape.utils import ManagerAccessMixin
from eip712 import EIP712Message, EIP712Type

if TYPE_CHECKING:
    from ape.api import ReceiptAPI
    from ape.types import AddressType
    from packaging.version import Version
    from ruffsack.main import Ruffsack


class Call(EIP712Type):
    target: "address"  # type: ignore[name-defined]  # noqa: F821
    value: "uint256"  # type: ignore[name-defined]  # noqa: F821
    data: "bytes"


class ExecuteBase(EIP712Message):
    _name_ = "Ruffsack Wallet"

    parent: "bytes32"  # type: ignore[name-defined]  # noqa: F821
    calls: list[Call] = []


class Execute(ManagerAccessMixin):
    def __init__(
        self,
        sack: "Ruffsack | None" = None,
        parent: HexBytes | None = None,
        version: "Version | None" = None,
        address: "AddressType | None" = None,
        chain_id: int | None = None,
    ):
        self.sack = sack

        if not chain_id:
            chain_id = self.chain_manager.chain_id

        if not (parent and version and address):
            if not sack:
                raise ValueError("Must provide either `sack=` or the remaining kwargs.")

            parent = sack.head
            version = sack.version
            address = sack.address

        class Execute(ExecuteBase):
            _verifyingContract_ = address
            _version_ = str(version)
            _chainId_ = chain_id

        self.message = Execute(parent=parent)

    def add_raw(self, target: "AddressType", value: int = 0, data: bytes = b"") -> Self:
        self.message.calls.append(Call(target=target, value=value, data=data))
        return self

    def add(self, call, *args, value: int = 0) -> Self:
        return self.add_raw(
            target=call.contract.address,
            value=value,
            data=call.encode_input(*args),
        )

    def __call__(
        self, sack: "Ruffsack | None" = None, **txn_args
    ) -> "ReceiptAPI | None":
        if not (sack or (sack := self.sack)):
            raise RuntimeError("Must provider `sack=` to execute")

        return sack.execute(self, **txn_args)
