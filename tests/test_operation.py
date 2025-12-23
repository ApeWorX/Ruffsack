import ape
import pytest


def test_configuration(networks, van, VERSION, THRESHOLD, owners):
    assert set(van.signers) == set(o.address for o in owners)
    assert van.threshold == THRESHOLD

    assert van.admin_guard is None
    assert van.execute_guard is None

    enabled, name, version, chain_id, address, salt, extensions = (
        van.contract.eip712Domain()
    )
    assert enabled == b"\x0f"  # NOTE: all but `salt` is enabled
    assert name == "Caravan Wallet"
    assert version == str(VERSION)
    assert chain_id == networks.provider.chain_id
    assert address == van.address
    assert salt == b"\x00" * 32
    assert extensions == []


def test_initialize(singleton, van, THRESHOLD, owners):
    assert van.contract.IMPLEMENTATION() == singleton

    with ape.reverts():  # dev_message="only Proxy can initialize"):
        # NOTE: Can't initialize singleton
        singleton.initialize(owners, THRESHOLD, sender=owners[0])

    with ape.reverts():  # dev_message="can only initialize once"):
        # NOTE: Can't initialize proxy a second time
        van.contract.initialize(owners, THRESHOLD, sender=owners[0])


@pytest.mark.parametrize("calls", ["0_calls", "1_call", "2_calls"])
def test_execute(accounts, van, owners, calls):
    msg = van.new_batch()

    for idx in range(total_calls := int(calls.split("_")[0])):
        msg.add_raw(
            target=accounts[idx].address,
            value=idx,
            data=f"{idx}".encode("utf-8"),
        )

    assert van.head == msg.parent
    assert msg not in van.queue

    van.stage(msg)
    assert msg in van.queue

    receipt = van.commit(msg, sender=owners[0])
    assert van.head == msg.hash

    if total_calls > 0:
        assert receipt.events == [
            van.contract.Executed(
                executor=owners[0],
                target=account,
                value=idx,
                data=f"{idx}".encode("utf-8"),
            )
            for idx, account in enumerate(accounts[:total_calls])
        ]

    else:
        assert receipt.events == []
