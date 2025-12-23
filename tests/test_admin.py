from packaging.version import Version
from ruffsack.messages import ActionType


def test_upgrade(VERSION, owners, create_release, singleton, sack):
    new_version = Version(f"{VERSION}+post.0")
    new_impl = create_release(version=new_version)

    msg = ActionType.UPGRADE_IMPLEMENTATION(new_impl.address, sack=sack)
    assert sack.head == msg.parent
    assert msg not in sack.queue

    sack.stage(msg)
    assert msg in sack.queue

    receipt = sack.commit(msg, sender=owners[0])
    assert sack.head == msg.hash

    assert receipt.events == [
        sack.contract.ImplementationUpgraded(
            executor=owners[0],
            old=singleton,
            new=new_impl,
        ),
    ]
    assert sack.contract.IMPLEMENTATION() == new_impl


def test_rotate_signers(accounts, owners, sack):
    msg = ActionType.ROTATE_SIGNERS(
        [accounts[len(owners)].address],
        [owners[0].address],
        sack.threshold,
        sack=sack,
    )
    assert sack.head == msg.parent
    assert msg not in sack.queue

    sack.stage(msg)
    assert msg in sack.queue

    receipt = sack.commit(msg, sender=owners[0])
    assert sack.head == msg.hash

    assert receipt.events == [
        sack.contract.SignersRotated(
            executor=owners[0],
            num_signers=len(owners),
            threshold=sack.threshold,
            signers_added=[accounts[len(owners)]],
            signers_removed=[owners[0]],
        ),
    ]
    assert sack.signers[0] == accounts[1]
    assert sack.signers[len(owners) - 1] == accounts[len(owners)]
