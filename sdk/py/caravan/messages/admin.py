from enum import Flag
from typing import TYPE_CHECKING

from eip712 import EIP712Message, EIP712Domain, hash_message
from eth_abi import encode as abi_encode, decode as abi_decode
from eth_pydantic_types import abi, HexBytes
from eth_pydantic_types.hex.bytes import HexBytes32

if TYPE_CHECKING:
    from ape.types.address import AddressType
    from packaging.version import Version

    from .main import Caravan


class Modify(EIP712Message):
    parent: abi.bytes32  # type: ignore[name-defined]  # noqa: F821
    action: abi.uint256  # type: ignore[name-defined]  # noqa: F821
    data: HexBytes

    @property
    def hash(self) -> HexBytes32:
        return hash_message(self)

    def render(self) -> dict:
        t = ActionType(self.action)
        data = {"Action": t.name.replace("_", " ").capitalize()}
        data.update(
            dict(
                zip(
                    TYPES[t].keys(),
                    abi_decode(tuple(TYPES[t].values()), self.data),
                )
            )
        )
        return data


class ActionType(Flag):
    UPGRADE_IMPLEMENTATION = 1
    ROTATE_SIGNERS = 2
    CONFIGURE_MODULE = 4
    SET_ADMIN_GUARD = 8
    SET_EXECUTE_GUARD = 16
    # NOTE: Add future reconfiguration actions here

    def __call__(
        self,
        *args,
        version: "Version | None" = None,
        address: "AddressType | None" = None,
        chain_id: int | None = None,
        parent: bytes | None = None,
        van: "Caravan | None" = None,
    ) -> Modify:
        assert van or all((version, address, chain_id, parent))
        eip712_domain = EIP712Domain(
            name="Caravan Wallet",
            verifyingContract=address or van.address,
            version=str(version or van.version),
            chainId=chain_id or van.provider.chain_id,
        )

        return Modify(
            parent=parent or van.head,
            action=self.value,
            data=abi_encode(tuple(TYPES[self].values()), args),
            eip712_domain=eip712_domain,
        )


TYPES: dict[ActionType, dict[str, str]] = {
    ActionType.UPGRADE_IMPLEMENTATION: {"New Implementation": "address"},
    ActionType.ROTATE_SIGNERS: {
        "Signers to Add": "address[]",
        "Signers to Remove": "address[]",
        "Threshold": "uint256",
    },
    ActionType.CONFIGURE_MODULE: {
        "Module": "address",
        "Enabled": "bool",
    },
    ActionType.SET_ADMIN_GUARD: {"New Admin Guard": "address"},
    ActionType.SET_EXECUTE_GUARD: {"New Execute Guard": "address"},
}
