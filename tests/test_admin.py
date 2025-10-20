from ruffsack.messages import ActionType


def test_upgrade(
    chain, VERSION, THRESHOLD, singleton, create_release, sack, owners, approval_flow
):
    new_impl = create_release()

    msg = ActionType.UPGRADE_IMPLEMENTATION(
        sack.head(),
        new_impl.address,
        version=VERSION,
        address=sack.address,
        chain_id=chain.chain_id,
    )

    args = [msg.action, msg.data]
    if approval_flow == "onchain":
        for owner in owners[:THRESHOLD]:
            sack.set_approval(msg._message_hash_, sender=owner)

    else:
        args.append([o.sign_message(msg).encode_rsv() for o in owners])

    receipt = sack.modify(*args, sender=owners[0])

    assert receipt.events == [
        sack.ImplementationUpgraded(
            executor=owners[0],
            old=singleton,
            new=new_impl,
        ),
    ]
    assert sack.IMPLEMENTATION() == new_impl

    assert sack.head() == msg._message_hash_


def test_rotate_signers(
    accounts, chain, VERSION, THRESHOLD, sack, owners, approval_flow
):
    msg = ActionType.ROTATE_SIGNERS(
        sack.head(),
        [accounts[len(owners)].address],
        [owners[0].address],
        sack.threshold(),
        version=VERSION,
        address=sack.address,
        chain_id=chain.chain_id,
    )

    args = [msg.action, msg.data]
    if approval_flow == "onchain":
        for owner in owners[:THRESHOLD]:
            sack.set_approval(msg._message_hash_, sender=owner)

    else:
        args.append([o.sign_message(msg).encode_rsv() for o in owners])

    receipt = sack.modify(*args, sender=owners[0])

    assert receipt.events == [
        sack.SignersRotated(
            executor=owners[0],
            num_signers=len(owners),
            threshold=sack.threshold(),
            signers_added=[accounts[len(owners)]],
            signers_removed=[owners[0]],
        ),
    ]
    assert sack.signers(0) == accounts[1]
    assert sack.signers(len(owners) - 1) == accounts[len(owners)]

    assert sack.head() == msg._message_hash_
