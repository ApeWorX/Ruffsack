from enum import Flag

from ape.types.address import AddressType
from eip712 import EIP712Message
from eth_abi import encode as abi_encode
from packaging.version import Version


class ModifyBase(EIP712Message):
    _name_ = "Ruffsack Wallet"
    parent: "bytes32"
    action: "uint256"  # type: ignore
    data: "bytes"


class ActionType(Flag):
    UPGRADE_IMPLEMENTATION = 1
    ROTATE_SIGNERS = 2
    CONFIGURE_MODULE = 4
    SET_ADMIN_GUARD = 8
    SET_EXECUTE_GUARD = 16
    # NOTE: Add future reconfiguration actions here

    def __call__(
        self,
        parent: bytes,
        *args,
        version: Version | None = None,
        address: AddressType | None = None,
        chain_id: int = 1,
    ) -> ModifyBase:
        class Modify(ModifyBase):
            _verifyingContract_ = address
            _version_ = str(version)
            _chainId_ = chain_id

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

        return Modify(  # type: ignore[call-arg]
            parent=parent,
            action=self.value,
            data=abi_encode(arg_types, args),
        )
