from ruffsack.messages import ActionType


def test_upgrade(chain, VERSION, singleton, create_release, sack, owners):
    new_impl = create_release()

    msg = ActionType.UPGRADE_IMPLEMENTATION(
        new_impl.address,
        version=VERSION,
        address=sack.address,
        chain_id=chain.chain_id,
    )
    signatures = [o.sign_message(msg).encode_rsv() for o in owners]
    receipt = sack.modify(msg.action, msg.data, signatures, sender=owners[0])

    assert receipt.events == [
        sack.ImplementationUpgraded(
            executor=owners[0],
            old=singleton,
            new=new_impl,
        ),
    ]
    assert sack.IMPLEMENTATION() == new_impl


def test_rotate_signers(accounts, chain, VERSION, sack, owners):
    msg = ActionType.ROTATE_SIGNERS(
        [accounts[len(owners)].address],
        [owners[0].address],
        sack.threshold(),
        version=VERSION,
        address=sack.address,
        chain_id=chain.chain_id,
    )
    signatures = [o.sign_message(msg).encode_rsv() for o in owners]
    receipt = sack.modify(msg.action, msg.data, signatures, sender=owners[0])

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
