from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, ClassVar, Self

from ape.api.accounts import ImpersonatedAccount
from ape.utils import ManagerAccessMixin
from eip712 import EIP712Domain, EIP712Message, hash_message
from eth_pydantic_types import HexBytes, HexBytes32, abi
from pydantic import BaseModel, PrivateAttr

if TYPE_CHECKING:
    from ape.api import ReceiptAPI
    from ape.api.address import BaseAddress
    from ape.types import AddressType
    from packaging.version import Version

    from ..main import Caravan
    from ..queue import QueueItem


class Call(BaseModel):
    target: abi.address
    value: abi.uint256
    success_required: bool
    data: HexBytes

    def render(self) -> str:
        return f"{self.target}({self.data}, value={self.value}, required={self.success_required})"


class Execute(EIP712Message, ManagerAccessMixin):
    MAX_CALLS: ClassVar[int] = 8
    MAX_CALLDATA_SIZE: ClassVar[int] = 16_388

    parent: abi.bytes32
    calls: list[Call] = []

    _van: "Caravan | None" = PrivateAttr(default=None)

    @property
    def hash(self) -> HexBytes32:
        return hash_message(self)

    def render(self) -> dict:
        if self.calls:
            return {
                "Action": "Execute",
                "Calls": [call.render() for call in self.calls],
            }

        return {"Action": "No-op"}

    @classmethod
    def new(
        cls,
        van: "Caravan | None" = None,
        parent: abi.bytes32 | None = None,
        version: "Version | None" = None,
        address: "AddressType | None" = None,
        chain_id: int | None = None,
    ):
        if not ((parent and version and address) or van):
            raise ValueError("Must provide either `van=` or the remaining kwargs.")

        eip712_domain = EIP712Domain(
            name="Caravan Wallet",
            verifyingContract=address or van.address,
            version=str(version) if version else str(van.version),
            chainId=chain_id or cls.chain_manager.chain_id,
        )

        self = cls(parent=parent or van.head, eip712_domain=eip712_domain)
        self._van = van  # NOTE: Set private variable
        return self

    def add_raw(
        self,
        target: "BaseAddress | AddressType | str",
        value: str | int = 0,
        success_required: bool = True,
        data: HexBytes = b"",
    ) -> Self:
        if len(self.calls) >= self.MAX_CALLS:
            raise RuntimeError(
                "Caravan does not support more than 8 calls per execute transaction."
            )

        if len(data) > self.MAX_CALLDATA_SIZE:
            raise RuntimeError(
                "Caravan calls do not support data field larger than"
                f" {self.MAX_CALLDATA_SIZE} bytes."
            )

        # NOTE: Avoid imports otherwise just for typing
        from ape.types import AddressType

        self.calls.append(
            Call(
                target=self.conversion_manager.convert(target, AddressType),
                value=self.conversion_manager.convert(value, int),
                success_required=success_required,
                data=data,
            )
        )
        return self

    def add(self, call, *args, value: int = 0, success_required: bool = True) -> Self:
        return self.add_raw(
            target=call.contract,
            value=value,
            success_required=success_required,
            data=call.encode_input(*args),
        )

    def add_transfer(
        self,
        target: "BaseAddress | AddressType | str",
        value: int | str,
        data: bytes = b"",
        success_required: bool = True,
    ):
        return self.add_raw(
            target=target,
            value=value,
            success_required=success_required,
            data=data,  # In case you want to add a message or something
        )

    def add_from_receipt(
        self, receipt: "ReceiptAPI", success_required: bool = True
    ) -> Self:
        return self.add_raw(
            target=receipt.receiver,
            value=receipt.value,
            success_required=success_required,
            data=receipt.data,
        )

    @contextmanager
    def add_from_simulation(self) -> Generator[ImpersonatedAccount, None, None]:
        if not self._van:
            raise RuntimeError("Only use simulations with an 'attached' batch instance")

        with (
            self.chain_manager.isolate()
            if self.provider.network.is_dev
            else self.network_manager.fork()
        ):
            with self.account_manager.use_sender(self._van.address) as van_account:
                starting_nonce = van_account.nonce
                yield van_account

            for txn in van_account.history[starting_nonce:]:
                self.add_from_receipt(txn)

    def stage(self, van: "Caravan | None" = None) -> "QueueItem":
        if not (van or (van := self._van)):
            raise RuntimeError("Must provider `van=` to execute")

        return van.stage(self)

    def __call__(self, van: "Caravan | None" = None, **txn_args) -> "ReceiptAPI | None":
        if not (van or (van := self._van)):
            raise RuntimeError("Must provider `van=` to execute")

        return van.commit(self, **txn_args)
