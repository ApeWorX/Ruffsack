# @version 0.4.3
"""
@title Ruffsack
@license Apache-2.0
@author ApeWorX LTD.
"""

NAME: constant(String[15]) = "Ruffsack Wallet"
NAMEHASH: constant(bytes32) = keccak256(NAME)
# NOTE: Update this before each release (controls EIP712 Domain)
VERSION: public(constant(String[10])) = "0.1"
VERSIONHASH: constant(bytes32) = keccak256(VERSION)

EIP712_DOMAIN_TYPEHASH: constant(bytes32) = keccak256(
    "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)
MODIFY_TYPEHASH: constant(bytes32) = keccak256(
    "Modify(uint256 action,bytes data)"
)

struct Call:
    target: address
    value: uint256
    # TODO: Increase size to 65540 once Vyper improves memory allocation (gas costs too high)
    data: Bytes[16388]


CALL_TYPEHASH: constant(bytes32) = keccak256(
    "Call(address target,uint256 value,bytes data)"
)
EXECUTE_TYPEHASH: constant(bytes32) = keccak256(
    "Execute(Call[] calls)Call(address target,uint256 value,bytes data)"
)

# @dev The current implementation address for `RuffsackProxy`
IMPLEMENTATION: public(address)
# NOTE: Must be first slot, this will be used by upgradeable proxy for delegation

# Signer properties
# @dev All current signers (unordered)
signers: public(DynArray[address, 11])
# @dev Number of signers required to execute an action
threshold: public(uint256)
# NOTE: invariant `0 < threshold <= len(signers)`

flag ActionType:
    UPGRADE_IMPLEMENTATION
    ROTATE_SIGNERS
    CONFIGURE_MODULE
    SET_ADMIN_GUARD
    SET_EXECUTE_GUARD
    # NOTE: Add future reconfiguration actions here

interface IAdminGuard:
    def preUpdateCheck(action: ActionType, data: Bytes[65535]): nonpayable
    def postUpdateCheck(): nonpayable

# @dev Before/after checker for Update actions
admin_guard: public(IAdminGuard)

interface IExecuteGuard:
    def preExecuteCheck(call: Call): nonpayable
    def postExecuteCheck(): nonpayable

# @dev Before/after checker for Execute actions
execute_guard: public(IExecuteGuard)

# @dev Modules enabled for this wallet
module_enabled: public(HashMap[address, bool])


# NOTE: Future variables (used for new core features) must be added below


# NOTE: All admin events are separated out
event ImplementationUpgraded:
    executor: indexed(address)
    old: indexed(address)
    new: indexed(address)


event SignersRotated:
    executor: indexed(address)
    num_signers: indexed(uint256)
    threshold: indexed(uint256)
    signers_added: DynArray[address, 11]
    signers_removed: DynArray[address, 11]


event ModuleUpdated:
    executor: indexed(address)
    module: indexed(address)
    enabled: indexed(bool)


event AdminGuardUpdated:
    executor: indexed(address)
    old: indexed(IAdminGuard)
    new: indexed(IAdminGuard)


event ExecuteGuardUpdated:
    executor: indexed(address)
    old: indexed(IExecuteGuard)
    new: indexed(IExecuteGuard)


event Executed:
    executor: indexed(address)
    success: indexed(bool)
    target: indexed(address)
    value: uint256
    data: Bytes[16388]


# NOTE: IERC5267
@view
@external
def eip712Domain() -> (
    bytes1,
    String[50],
    String[20],
    uint256,
    address,
    bytes32,
    DynArray[uint256, 32],
):
    return (
        # NOTE: `0x0f` equals `01111` (`salt` is not used)
        0x0f,
        NAME,
        VERSION,
        chain.id,
        self,
        empty(bytes32), # Salt is ignored
        empty(DynArray[uint256, 32]),  # No extensions
    )


@external
def initialize(signers: DynArray[address, 11], threshold: uint256):
    assert self.IMPLEMENTATION != empty(address)  # dev: only Proxy can initialize
    assert self.threshold == 0  # dev: can only initialize once
    assert threshold > 0 and threshold <= len(signers)

    self.signers = signers
    self.threshold = threshold


def _verify_signatures(msghash: bytes32, signatures: DynArray[Bytes[65], 11]):
    assert len(signatures) >= self.threshold
    signers: DynArray[address, 11] = self.signers

    already_approved: DynArray[address, 11] = []
    for sig: Bytes[65] in signatures:
        # NOTE: Signatures should be 65 bytes in RSV order
        r: bytes32 = convert(slice(sig, 0, 32), bytes32)
        s: bytes32 = convert(slice(sig, 32, 32), bytes32)
        v: uint8 = convert(slice(sig, 64, 1), uint8)
        signer: address = ecrecover(msghash, v, r, s)
        assert signer in signers, "Invalid Signer"
        assert signer not in already_approved, "Signer cannot approve twice"
        already_approved.append(signer)


@view
def _DOMAIN_SEPARATOR() -> bytes32:
    return keccak256(
        abi_encode(EIP712_DOMAIN_TYPEHASH, NAMEHASH, VERSIONHASH, chain.id, self)
    )


@view
@external
def DOMAIN_SEPARATOR() -> bytes32:
    return self._DOMAIN_SEPARATOR()


@view
def _hash_typed_data_v4(struct_hash: bytes32) -> bytes32:
    return keccak256(concat(x"1901", self._DOMAIN_SEPARATOR(), struct_hash))


def _rotate_signers(
    signers_to_add: DynArray[address, 11],
    signers_to_rm: DynArray[address, 11],
    threshold: uint256,
):
    current_signers: DynArray[address, 11] = self.signers
    new_signers: DynArray[address, 11] = []

    for signer: address in current_signers:
        if signer not in signers_to_rm:
            new_signers.append(signer)
        # else: skips adding `signer` to `new_signers`

    # NOTE: Ignores if `signer` in `signers_to_rm` not in `current_signers`

    for signer: address in signers_to_add:
        assert signer not in new_signers, "Signer cannot be added twice"
        new_signers.append(signer)

    if threshold > 0:
        assert threshold <= len(new_signers), "Invalid threshold"
        self.threshold = threshold

    self.signers = new_signers

    log SignersRotated(
        executor=msg.sender,
        num_signers=len(new_signers),
        threshold=self.threshold,  # NOTE: In case there was no change
        signers_added=signers_to_add,
        signers_removed=signers_to_rm,
    )


@external
def modify(
    action: ActionType,
    data: Bytes[65535],
    signatures: DynArray[Bytes[65], 11],
):
    msghash: bytes32 = self._hash_typed_data_v4(
        # NOTE: Per EIP712, Dynamic ABI types are encoded as the hash of their contents
        keccak256(abi_encode(MODIFY_TYPEHASH, action, keccak256(data)))
    )
    self._verify_signatures(msghash, signatures)

    admin_guard: IAdminGuard = self.admin_guard
    if admin_guard.address != empty(address):
        extcall admin_guard.preUpdateCheck(action, data)

    if action == ActionType.UPGRADE_IMPLEMENTATION:
        new: address = abi_decode(data, address)
        log ImplementationUpgraded(executor=msg.sender, old=self.IMPLEMENTATION, new=new)
        self.IMPLEMENTATION = new

    elif action == ActionType.ROTATE_SIGNERS:
        signers_to_add: DynArray[address, 11] = []
        signers_to_rm: DynArray[address, 11] = []
        threshold: uint256 = 0
        signers_to_add, signers_to_rm, threshold = abi_decode(
            data,
            (DynArray[address, 11], DynArray[address, 11], uint256),
        )
        self._rotate_signers(signers_to_add, signers_to_rm, threshold)

    elif action == ActionType.CONFIGURE_MODULE:
        module: address = empty(address)
        enabled: bool = False
        module, enabled = abi_decode(data, (address, bool))
        log ModuleUpdated(executor=msg.sender, module=module, enabled=enabled)
        self.module_enabled[module] = enabled

    elif action == ActionType.SET_ADMIN_GUARD:
        # NOTE: Don't use `admin_guard` as it would override above
        guard: IAdminGuard = abi_decode(data, IAdminGuard)
        log AdminGuardUpdated(executor=msg.sender, old=admin_guard, new=guard)
        self.admin_guard = guard

    elif action == ActionType.SET_EXECUTE_GUARD:
        guard: IExecuteGuard = abi_decode(data, IExecuteGuard)
        log ExecuteGuardUpdated(executor=msg.sender, old=self.execute_guard, new=guard)
        self.execute_guard = guard

    else:
        raise "Unsupported"

    if admin_guard.address != empty(address):
        # NOTE: We use the old admin guard to execute the check
        extcall admin_guard.postUpdateCheck()


@external
def execute(
    calls: DynArray[Call, 8],
    signatures: DynArray[Bytes[65], 11] = [],
):
    if not self.module_enabled[msg.sender]:
        # Hash message and validate signatures

        # Step 1: Encode struct to list of 32 byte hash of items
        encoded_call_members: DynArray[bytes32, 8] = []
        for call: Call in calls:
            encoded_call_members.append(
                # NOTE: Per EIP712, structs are encoded as the hash of their contents (incl. Typehash)
                keccak256(
                    abi_encode(
                        CALL_TYPEHASH,
                        call.target,
                        call.value,
                        # NOTE: Per EIP712, Dynamic ABI types are encoded as the hash of their contents
                        keccak256(call.data),
                    )
                )
            )

        # Step 2: Encode list of 32 byte items into single bytestring
        # NOTE: bytestring length including length because it's encoded as an array
        encoded_call_array: Bytes[32 * (8 + 1)] = abi_encode(encoded_call_members, ensure_tuple=False)
        # NOTE: Skip encoded length of encoded bytestring by slicing it off (start at byte 32)
        encoded_call_array = slice(encoded_call_array, 32, len(encoded_call_array) - 32)
        assert len(encoded_call_array) == 32 * len(calls)

        # Step 3: Hash concatenated item hashes, together with typehash, then with domain to get msghash
        msghash: bytes32 = self._hash_typed_data_v4(
            # NOTE: Per EIP712, Arrays are encoded as the hash of their encoded members, concated together
            keccak256(abi_encode(EXECUTE_TYPEHASH, keccak256(encoded_call_array)))
        )
        self._verify_signatures(msghash, signatures)

    guard: IExecuteGuard = self.execute_guard
    for call: Call in calls:
        if guard.address != empty(address):
            extcall guard.preExecuteCheck(call)

        # NOTE: No delegatecalls allowed (cannot modify configuration via `update` this way)
        success: bool = raw_call(
            call.target,
            call.data,
            value=call.value,
            revert_on_failure=False,
        )

        if guard.address != empty(address):
            extcall guard.postExecuteCheck()

        log Executed(
            executor=msg.sender,
            success=success,
            target=call.target,
            value=call.value,
            data=call.data,
        )
