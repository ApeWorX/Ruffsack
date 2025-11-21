from packaging.version import Version
from ruffsack.messages import ActionType


def test_upgrade(
    chain, VERSION, THRESHOLD, owners, create_release, singleton, sack, approval_flow
):
    new_version = Version(f"{VERSION}+post.0")
    new_impl = create_release(version=new_version)

    if approval_flow == "onchain":
        msg = ActionType.UPGRADE_IMPLEMENTATION(
            sack.head,
            new_impl.address,
            version=VERSION,
            address=sack.address,
            chain_id=chain.chain_id,
        )

        for owner in owners[:THRESHOLD]:
            sack.contract.set_approval(msg._message_hash_, sender=owner)

        receipt = sack.modify(msg, sender=owners[0])
        assert sack.head == msg._message_hash_

    else:
        receipt = sack.migrate(new_version=new_version, sender=owners[0])

    assert receipt.events == [
        sack.contract.ImplementationUpgraded(
            executor=owners[0],
            old=singleton,
            new=new_impl,
        ),
    ]
    assert sack.contract.IMPLEMENTATION() == new_impl


def test_rotate_signers(
    accounts, chain, VERSION, owners, THRESHOLD, sack, approval_flow
):
    if approval_flow == "onchain":
        msg = ActionType.ROTATE_SIGNERS(
            sack.head,
            [accounts[len(owners)].address],
            [owners[0].address],
            sack.threshold,
            version=VERSION,
            address=sack.address,
            chain_id=chain.chain_id,
        )

        for owner in owners[:THRESHOLD]:
            sack.contract.set_approval(msg._message_hash_, sender=owner)

        receipt = sack.modify(msg, sender=owners[0])
        assert sack.head == msg._message_hash_

    else:
        receipt = sack.rotate_signers(
            signers_to_add=[accounts[len(owners)]],
            signers_to_remove=[owners[0]],
            sender=owners[0],
        )

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
