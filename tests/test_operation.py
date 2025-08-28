import ape
from ape.utils.misc import ZERO_ADDRESS
from ruffsack.messages import create_execute_def


def test_configuration(networks, VERSION, THRESHOLD, owners, sack):
    assert set(sack.signers(idx) for idx in range(len(owners))) == set(
        o.address for o in owners
    )
    assert sack.threshold() == THRESHOLD

    assert sack.admin_guard() == ZERO_ADDRESS
    assert sack.execute_guard() == ZERO_ADDRESS

    enabled, name, version, chain_id, address, salt, extensions = sack.eip712Domain()
    assert enabled == b"\x0f"
    assert name == "Ruffsack Wallet"
    assert version == str(VERSION)
    assert chain_id == networks.provider.chain_id
    assert address == sack.address
    assert salt == b"\x00" * 32
    assert extensions == []


def test_initialize(THRESHOLD, owners, singleton, sack):
    assert sack.IMPLEMENTATION() == singleton

    with ape.reverts():  # dev_message="only Proxy can initialize"):
        # NOTE: Can't initialize singleton
        singleton.initialize(owners, THRESHOLD, sender=owners[0])

    with ape.reverts():  # dev_message="can only initialize once"):
        # NOTE: Can't initialize proxy a second time
        sack.initialize(owners, THRESHOLD, sender=owners[0])


def test_execute(chain, VERSION, owners, sack):
    Execute = create_execute_def(
        version=VERSION,
        address=sack.address,
        chain_id=chain.chain_id,
    )
    msg = Execute(target=owners[0].address, value=0, data=b"")
    signatures = [o.sign_message(msg).encode_rsv() for o in owners]
    receipt = sack.execute(*msg, signatures, sender=owners[0])

    assert receipt.events == [
        sack.Executed(
            executor=owners[0],
            target=owners[0],
            value=0,
            data=b"",
        ),
    ]
