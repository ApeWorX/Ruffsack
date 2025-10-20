# @version 0.4.3
"""
@title DaypackFactory
@license Apache-2.0
@author ApeWorX LTD.
"""

PROXY_INITCODE: public(immutable(Bytes[1024]))


# @dev The owner of the release registry that is allowed to add new releases.
governance: public(address)

interface IRuffsack:
    def VERSION() -> String[12]: view

# @dev The registered release implementations
releases: public(HashMap[String[12], address])
last_release: public(String[12])


event NewRelease:
    version: String[12]
    implementation: address


event NewRuffsack:
    deployer: indexed(address)
    # NOTE: If a dynamic type is indexed, it gets hashed
    version_hash: indexed(String[12])
    salt: indexed(bytes32)
    version: String[12]
    tag: String[64]
    signers: DynArray[address, 11]
    threshold: uint256
    new_sack: address


@deploy
def __init__(governance: address, proxy_initcode: Bytes[1024]):
    self.governance = governance
    PROXY_INITCODE = proxy_initcode


@external
def add_release(implementation: IRuffsack):
    assert msg.sender == self.governance

    version: String[12] = staticcall implementation.VERSION()
    assert self.releases[version] == empty(address)

    log NewRelease(version=version, implementation=implementation.address)
    self.releases[version] = implementation.address
    self.last_release = version


@external
def new(
    signers: DynArray[address, 11],
    threshold: uint256,
    version: String[12] = "stable",
    tag: String[64] = "",
) -> address:
    implementation: address = empty(address)
    if version == "stable":
        implementation = self.releases[self.last_release]
    else:
        implementation = self.releases[version]

    assert implementation != empty(address), "Invalid release"

    # NOTE: This does *not* depend on the version chosen by the user
    salt: bytes32 = keccak256(concat(abi_encode(signers, threshold), convert(tag, Bytes[64])))

    new_sack: address = raw_create(
        PROXY_INITCODE,
        implementation,
        signers,
        threshold,
        salt=salt,
    )
    log NewRuffsack(
        deployer=msg.sender,
        version_hash=version,
        salt=salt,
        version=version,
        tag=tag,
        signers=signers,
        threshold=threshold,
        new_sack=new_sack,
    )

    return new_sack
