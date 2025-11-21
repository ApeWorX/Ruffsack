from typing import TYPE_CHECKING, Any

from ape.contracts import ContractCall, ContractInstance
from ape.exceptions import AccountsError
from ape.types import AddressType, HexBytes, MessageSignature
from ape.utils import ZERO_ADDRESS, ManagerAccessMixin, cached_property
from ethpm_types.abi import ABIType, MethodABI
from packaging.version import Version

from .messages import ActionType, Execute
from .modules import ModuleManager
from .packages import PackageType, STABLE_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ape.api import AccountAPI, ReceiptAPI
    from eip712 import EIP712Message

    from .factory import Factory
    from .messages.admin import ModifyBase


# TODO: Subclass Ape's AccountAPI and make it a plugin
class Ruffsack(ManagerAccessMixin):
    def __init__(
        self,
        address: AddressType,
        version: Version | None = None,
        factory: "Factory | None" = None,
    ):
        self.address = address

        if factory:
            # NOTE: Override cached value
            self.factory = factory

        if version:
            # NOTE: Override cached value
            self.version = version

        # TODO: Add client support
        self.client = None

    @cached_property
    def factory(self) -> "Factory":
        from .factory import Factory

        return Factory()

    @cached_property
    def version(self) -> Version:
        # NOTE: Do this raw so we can determine the proper version to use
        call = ContractCall(
            abi=MethodABI(
                name="VERSION",
                stateMutability="pure",
                outputs=[ABIType(type="string")],
            ),
            address=self.address,
        )
        return Version(call())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.address} v{self.version})"

    @cached_property
    def contract(self) -> ContractInstance:
        return PackageType.SINGLETON(self.version).at(
            self.address,
            fetch_from_explorer=False,
            detect_proxy=False,
            # TODO: `proxy_info=self.contract.implementation()` using EIP-1967
        )

    @property
    def threshold(self) -> int:
        return self.contract.threshold()

    @property
    def signers(self) -> list[AddressType]:
        return self.contract.signers()

    @property
    def head(self) -> HexBytes:
        return self.contract.head()

    def set_head(self, new_head: HexBytes):
        # NOTE: allows modifying head for local simulation and testing
        # NOTE: Storage slot 1 in contract is head
        self.provider.set_storage(self.address, 1, new_head)

    @property
    def local_signers(self) -> list["AccountAPI"]:
        from ape.api.accounts import ImpersonatedAccount

        local_signers = []
        for signer_address in self.signers:
            try:
                signer = self.account_manager[signer_address]

            except AccountsError:
                continue

            if not isinstance(signer, ImpersonatedAccount):
                local_signers.append(signer)

        return local_signers

    def onchain_approvals(self, msghash: "HexBytes") -> int:
        return sum(
            map(int, map(lambda s: self.contract.approved(msghash, s), self.signers))
        )

    def get_signatures(
        self, msg: "EIP712Message", needed: int | None = None
    ) -> list[MessageSignature]:
        if needed is None:
            needed = self.threshold - self.onchain_approvals(msg._message_hash_)

        signatures = []

        if self.client:
            signatures.extend(self.client.get_signatures(msg._message_hash_))

        for signer in self.local_signers:
            if len(signatures) >= needed:
                # NOTE: In case using the client fetches enough signatures already
                break

            if signature := signer.sign_message(msg):
                signatures.append(signature)

        return signatures

    def modify(
        self, msg: "ModifyBase", submit: bool = True, **txn_args
    ) -> "ReceiptAPI | None":
        if submit and msg.parent != self.head:
            raise RuntimeError("Cannot execute call, wrong head")

        # TODO: Support `impersonate=True`

        needed = self.threshold - self.onchain_approvals(msg._message_hash_)
        if needed == 0 and submit:
            return self.contract.modify(msg.action, msg.data, **txn_args)

        signatures = self.get_signatures(msg, needed=needed)
        if (len(signatures) >= needed) and submit:
            return self.contract.modify(
                msg.action,
                msg.data,
                [sig.encode_rsv() for sig in signatures],
                **txn_args,
            )

        elif submit:
            raise RuntimeError(
                f"Not enough signatures, need {needed - len(signatures)} more"
            )

        elif self.client:
            # TODO: Add logging
            self.client.submit_signatures(msg, signatures)

        return None

    def migrate(
        self,
        new_version: Version | str = STABLE_VERSION,
        **txn_args,
    ) -> "ReceiptAPI | None":
        if not (release := self.factory.get_release(new_version)):
            raise ValueError(f"No release for {new_version} deployed on this chain")

        return self.modify(
            ActionType.UPGRADE_IMPLEMENTATION(
                release.address,
                sack=self,
            ),
            **txn_args,
        )

    def rotate_signers(
        self,
        signers_to_add: "Iterable[Any] | None" = None,
        signers_to_remove: "Iterable[Any] | None" = None,
        threshold: int = 0,
        **txn_args,
    ) -> "ReceiptAPI | None":
        signers_to_add = (
            [self.conversion_manager.convert(s, AddressType) for s in signers_to_add]
            if signers_to_add is not None
            else []
        )
        signers_to_remove = (
            [self.conversion_manager.convert(s, AddressType) for s in signers_to_remove]
            if signers_to_remove is not None
            else []
        )

        if invalid_signers := set(signers_to_remove) - set(signers := self.signers):
            raise ValueError(f"Can't remove signers: {', '.join(invalid_signers)}")

        elif invalid_signers := set(signers) & set(signers_to_add):
            raise ValueError(f"Can't add signers: {', '.join(invalid_signers)}")

        elif (
            threshold
            and (
                max_threshold := len(signers)
                + len(signers_to_add)
                - len(signers_to_remove)
            )
            < threshold
        ):
            raise ValueError(
                f"Can't set threshold to {threshold}, must be less than/equal to {max_threshold}."
            )

        return self.modify(
            ActionType.ROTATE_SIGNERS(
                signers_to_add,
                signers_to_remove,
                threshold,
                sack=self,
            ),
            **txn_args,
        )

    def add_signers(self, *signers: Any, **txn_args) -> "ReceiptAPI | None":
        return self.rotate_signers(signers_to_add=signers, **txn_args)

    def remove_signers(self, *signers: Any, **txn_args) -> "ReceiptAPI | None":
        return self.rotate_signers(signers_to_remove=signers, **txn_args)

    def change_threshold(self, threshold: int, **txn_args) -> "ReceiptAPI | None":
        return self.rotate_signers(threshold=threshold, **txn_args)

    @property
    def modules(self) -> ModuleManager:
        return ModuleManager(self)

    @property
    def admin_guard(self) -> ContractInstance | None:
        if (admin_guard := self.contract.admin_guard()) != ZERO_ADDRESS:
            return self.chain_manager.contracts.instance_at(admin_guard)

        return None

    def set_admin_guard(
        self, new_guard: Any = ZERO_ADDRESS, **txn_args
    ) -> "ReceiptAPI | None":
        new_guard = self.conversion_manager.convert(new_guard, AddressType)

        return self.modify(
            ActionType.SET_ADMIN_GUARD(new_guard, sack=self),
            **txn_args,
        )

    @admin_guard.setter
    def set_admin_guard_no_kwargs(self, new_guard: Any):
        self.set_admin_guard(new_guard)

    @admin_guard.deleter
    def delete_admin_guard_no_kwargs(self):
        self.set_admin_guard()

    @property
    def execute_guard(self) -> ContractInstance | None:
        if (execute_guard := self.contract.execute_guard()) != ZERO_ADDRESS:
            return self.chain_manager.contracts.instance_at(execute_guard)

        return None

    def set_execute_guard(
        self, new_guard: Any = ZERO_ADDRESS, **txn_args
    ) -> "ReceiptAPI | None":
        new_guard = self.conversion_manager.convert(new_guard, AddressType)

        return self.modify(
            ActionType.SET_EXECUTE_GUARD(new_guard, sack=self),
            **txn_args,
        )

    @execute_guard.setter
    def set_execute_guard_no_kwargs(self, new_guard: Any):
        self.set_execute_guard(new_guard)

    @execute_guard.deleter
    def delete_execute_guard_no_kwargs(self):
        self.set_execute_guard()

    def new_batch(self, parent: HexBytes | None = None) -> Execute:
        return Execute(sack=self, parent=parent)

    def execute(
        self, execution: Execute, submit: bool = True, **txn_args
    ) -> "ReceiptAPI | None":
        if submit and execution.message.parent != self.head:
            raise RuntimeError("Cannot execute call, wrong head")

        # TODO: Support `impersonate=True`
        needed = self.threshold - self.onchain_approvals(
            execution.message._message_hash_
        )
        if needed == 0 and submit:
            return self.contract.execute(execution.message.calls, **txn_args)

        signatures = self.get_signatures(execution.message, needed=needed)
        if (len(signatures) >= needed) and submit:
            return self.contract.execute(
                execution.message.calls,
                [sig.encode_rsv() for sig in signatures],
                **txn_args,
            )

        elif submit:
            raise RuntimeError(
                f"Not enough signatures, need {needed - len(signatures)} more"
            )

        elif self.client:
            # TODO: Add logging
            self.client.submit_signatures(execution.message, signatures)

        return None
