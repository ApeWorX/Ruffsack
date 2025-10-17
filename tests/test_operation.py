import ape
import pytest
from ape.utils.misc import ZERO_ADDRESS
from ruffsack.messages import Execute


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


@pytest.mark.parametrize("calls", ["0_calls", "1_call", "2_calls"])
def test_execute(
    accounts, chain, VERSION, THRESHOLD, owners, sack, approval_flow, calls
):
    txn = Execute(
        version=VERSION,
        address=sack.address,
        chain_id=chain.chain_id,
    )

    for idx in range(total_calls := int(calls.split("_")[0])):
        txn.add_raw(
            target=accounts[idx].address,
            value=idx,
            data=f"{idx}".encode("utf-8"),
        )

    args = [txn.message.calls]
    if approval_flow == "onchain":
        for owner in owners[:THRESHOLD]:
            sack.set_approval(txn.message._message_hash_, sender=owner)

    else:
        args.append([o.sign_message(txn.message).encode_rsv() for o in owners])

    receipt = sack.execute(*args, sender=owners[0])

    assert receipt.events == (
        [
            sack.Executed(
                executor=owners[0],
                target=account,
                value=idx,
                data=f"{idx}".encode("utf-8"),
            )
            for idx, account in enumerate(accounts[:total_calls])
        ]
        if total_calls > 0
        else []
    )
