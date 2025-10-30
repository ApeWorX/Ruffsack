from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Self

from ape.api.accounts import ImpersonatedAccount
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
    MAX_CALLS = 8
    MAX_CALLDATA_SIZE = 16_388

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
        if len(self.message.calls) >= self.MAX_CALLS:
            raise RuntimeError(
                "Ruffsack does not support more than 8 calls per execute transaction."
            )

        if len(data) > self.MAX_CALLDATA_SIZE:
            raise RuntimeError(
                "Ruffsack calls do not support data field larger than"
                f" {self.MAX_CALLDATA_SIZE} bytes."
            )

        self.message.calls.append(Call(target=target, value=value, data=data))
        return self

    def add(self, call, *args, value: int = 0) -> Self:
        return self.add_raw(
            target=call.contract.address,
            value=value,
            data=call.encode_input(*args),
        )

    def add_from_receipt(self, receipt: "ReceiptAPI") -> Self:
        return self.add_raw(
            target=receipt.receiver,
            value=receipt.value,
            data=receipt.data,
        )

    @contextmanager
    def add_from_simulation(self) -> Generator[ImpersonatedAccount, None, None]:
        if not self.sack:
            raise RuntimeError("Only use simulations with an 'attached' batch instance")

        with (
            self.chain_manager.isolate()
            if self.provider.network.is_local
            else self.chain_manager.fork()
        ):
            with self.account_manager.use_sender(self.sack.address) as sack_account:
                starting_nonce = sack_account.nonce
                yield sack_account

            for txn in sack_account.history[starting_nonce:]:
                self.add_from_receipt(txn)

    def __call__(
        self, sack: "Ruffsack | None" = None, **txn_args
    ) -> "ReceiptAPI | None":
        if not (sack or (sack := self.sack)):
            raise RuntimeError("Must provider `sack=` to execute")

        return sack.execute(self, **txn_args)
