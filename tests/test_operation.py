import ape
import pytest


def test_configuration(networks, sack, VERSION, THRESHOLD, owners):
    assert set(sack.signers) == set(o.address for o in owners)
    assert sack.threshold == THRESHOLD

    assert sack.admin_guard is None
    assert sack.execute_guard is None

    enabled, name, version, chain_id, address, salt, extensions = (
        sack.contract.eip712Domain()
    )
    assert enabled == b"\x0f"  # NOTE: all but `salt` is enabled
    assert name == "Ruffsack Wallet"
    assert version == str(VERSION)
    assert chain_id == networks.provider.chain_id
    assert address == sack.address
    assert salt == b"\x00" * 32
    assert extensions == []


def test_initialize(singleton, sack, THRESHOLD, owners):
    assert sack.contract.IMPLEMENTATION() == singleton

    with ape.reverts():  # dev_message="only Proxy can initialize"):
        # NOTE: Can't initialize singleton
        singleton.initialize(owners, THRESHOLD, sender=owners[0])

    with ape.reverts():  # dev_message="can only initialize once"):
        # NOTE: Can't initialize proxy a second time
        sack.contract.initialize(owners, THRESHOLD, sender=owners[0])


@pytest.mark.parametrize("calls", ["0_calls", "1_call", "2_calls"])
def test_execute(accounts, sack, THRESHOLD, owners, approval_flow, calls):
    txn = sack.new_batch()

    for idx in range(total_calls := int(calls.split("_")[0])):
        txn.add_raw(
            target=accounts[idx].address,
            value=idx,
            data=f"{idx}".encode("utf-8"),
        )

    if approval_flow == "onchain":
        for owner in owners[:THRESHOLD]:
            sack.contract.set_approval(txn.hash, sender=owner)

    assert (receipt := sack.execute(txn, sender=owners[0]))

    if total_calls > 0:
        assert receipt.events == [
            sack.contract.Executed(
                executor=owners[0],
                target=account,
                value=idx,
                data=f"{idx}".encode("utf-8"),
            )
            for idx, account in enumerate(accounts[:total_calls])
        ]

    else:
        assert receipt.events == []

    assert sack.head == txn.hash
