from enum import Flag
from typing import TYPE_CHECKING

from eip712 import EIP712Message, EIP712Domain, hash_message
from eth_abi import encode as abi_encode
from eth_pydantic_types import abi, HexBytes
from eth_pydantic_types.hex.bytes import HexBytes32

if TYPE_CHECKING:
    from ape.types.address import AddressType
    from packaging.version import Version

    from .main import Ruffsack


class Modify(EIP712Message):
    parent: abi.bytes32  # type: ignore[name-defined]  # noqa: F821
    action: abi.uint256  # type: ignore[name-defined]  # noqa: F821
    data: HexBytes

    @property
    def hash(self) -> HexBytes32:
        return hash_message(self)


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
        sack: "Ruffsack | None" = None,
    ) -> Modify:
        assert sack or all((version, address, chain_id, parent))
        eip712_domain = EIP712Domain(
            name="Ruffsack Wallet",
            verifyingContract=address or sack.address,
            version=str(version or sack.version),
            chainId=chain_id or sack.provider.chain_id,
        )

        arg_types: tuple[str, ...]
        match self:
            case ActionType.UPGRADE_IMPLEMENTATION:
                arg_types = ("address",)
            case ActionType.ROTATE_SIGNERS:
                arg_types = ("address[]", "address[]", "uint256")
            case ActionType.CONFIGURE_MODULE:
                arg_types = ("address", "bool")
            case ActionType.SET_ADMIN_GUARD:
                arg_types = ("address",)
            case ActionType.SET_EXECUTE_GUARD:
                arg_types = ("address",)

        return Modify(
            parent=parent or sack.head,
            action=self.value,
            data=abi_encode(arg_types, args),
            eip712_domain=eip712_domain,
        )
