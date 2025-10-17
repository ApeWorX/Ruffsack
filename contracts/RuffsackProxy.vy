# @version 0.4.3
"""
@title RuffsackProxy
@license Apache-2.0
@author ApeWorX LTD.
"""

# NOTE: Must be first slot, this matches the same storage variable in `Ruffsack`
IMPLEMENTATION: address

# NOTE: NO OTHER VARIABLES ALLOWED


@deploy
def __init__(
    implementation: address,
    signers: DynArray[address, 11],
    threshold: uint256,
):
    self.IMPLEMENTATION = implementation
    raw_call(
        implementation,
        abi_encode(signers, threshold, method_id=method_id("initialize(address[],uint256)")),
        is_delegate_call=True,
    )


@payable
@external
@raw_return
def __default__() -> Bytes[65535]:
    if msg.value == 0:
        return raw_call(
            self.IMPLEMENTATION,
            msg.data,
            is_delegate_call=True,
            max_outsize=65535,
        )
    # else: Accept ether (do nothing)
    return b""
