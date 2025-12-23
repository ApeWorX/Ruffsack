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
    from ape.types import AddressType
    from packaging.version import Version

    from ..main import Caravan
    from ..queue import QueueItem


class Call(BaseModel):
    target: abi.address
    value: abi.uint256
    data: HexBytes

    def render(self) -> str:
        return f"{self.target}({self.data}, value={self.value})"


class Execute(EIP712Message, ManagerAccessMixin):
    MAX_CALLS: ClassVar[int] = 8
    MAX_CALLDATA_SIZE: ClassVar[int] = 16_388

    parent: abi.bytes32
    calls: list[Call] = []

    _sack: "Caravan | None" = PrivateAttr(default=None)

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
        sack: "Caravan | None" = None,
        parent: abi.bytes32 | None = None,
        version: "Version | None" = None,
        address: "AddressType | None" = None,
        chain_id: int | None = None,
    ):
        if not ((parent and version and address) or sack):
            raise ValueError("Must provide either `sack=` or the remaining kwargs.")

        eip712_domain = EIP712Domain(
            name="Caravan Wallet",
            verifyingContract=address or sack.address,
            version=str(version) if version else str(sack.version),
            chainId=chain_id or cls.chain_manager.chain_id,
        )

        self = cls(parent=parent or sack.head, eip712_domain=eip712_domain)
        self._sack = sack  # NOTE: Set private variable
        return self

    def add_raw(
        self, target: "AddressType", value: int = 0, data: HexBytes = b""
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

        self.calls.append(Call(target=target, value=value, data=data))
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
        if not self._sack:
            raise RuntimeError("Only use simulations with an 'attached' batch instance")

        with (
            self.chain_manager.isolate()
            if self.provider.network.is_local
            else self.network_manager.fork()
        ):
            with self.account_manager.use_sender(self._sack.address) as sack_account:
                starting_nonce = sack_account.nonce
                yield sack_account

            for txn in sack_account.history[starting_nonce:]:
                self.add_from_receipt(txn)

    def stage(self, sack: "Caravan | None" = None) -> "QueueItem":
        if not (sack or (sack := self._sack)):
            raise RuntimeError("Must provider `sack=` to execute")

        return sack.stage(self)

    def __call__(
        self, sack: "Caravan | None" = None, **txn_args
    ) -> "ReceiptAPI | None":
        if not (sack or (sack := self._sack)):
            raise RuntimeError("Must provider `sack=` to execute")

        return sack.commit(self, **txn_args)
