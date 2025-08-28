from ape.types.address import AddressType
from eip712 import EIP712Message
from packaging.version import Version


# TODO: Refactor this to a multicall-like object
class ExecuteBase(EIP712Message):
    _name_ = "Ruffsack Wallet"
    target: "address"  # type: ignore
    value: "uint256"  # type: ignore
    data: "bytes"


def create_def(
    version: Version,
    address: AddressType,
    chain_id: int,
) -> type[ExecuteBase]:
    class Execute(ExecuteBase):
        _verifyingContract_ = address
        _version_ = str(version)
        _chainId_ = chain_id

    return Execute
