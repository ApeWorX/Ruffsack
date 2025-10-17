from typing import TYPE_CHECKING, Self

from ape.utils import ManagerAccessMixin
from eip712 import EIP712Message, EIP712Type

if TYPE_CHECKING:
    from ape.types import AddressType
    from packaging.version import Version


class Call(EIP712Type):
    target: "address"  # type: ignore
    value: "uint256"  # type: ignore
    data: "bytes"


class ExecuteBase(EIP712Message):
    _name_ = "Ruffsack Wallet"

    calls: list[Call] = []


class Execute(ManagerAccessMixin):
    def __init__(self, version: "Version", address: "AddressType", chain_id: int):
        class Execute(ExecuteBase):
            _verifyingContract_ = address
            _version_ = str(version)
            _chainId_ = chain_id

        self.message = Execute()

    def add_raw(self, target: "AddressType", value: int = 0, data: bytes = b"") -> Self:
        self.message.calls.append(Call(target=target, value=value, data=data))
        return self

    def add(self, call, *args, value: int = 0) -> Self:
        return self.add_raw(
            target=call.contract.address,
            value=value,
            data=call.encode_input(*args),
        )
