from typing import TYPE_CHECKING, Any

from ape.types import AddressType
from ape.utils import ManagerAccessMixin

from .messages import ActionType

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ape.api import ReceiptAPI
    from ape.contracts import ContractInstance

    from .main import Ruffsack


class ModuleManager(ManagerAccessMixin):
    def __init__(self, sack: "Ruffsack"):
        self.sack = sack

        self._cached_modules: set["ContractInstance"] = set()
        self._last_cached: int = 0

    def _update_cache(self):
        for log in self.sack.contract.ModuleUpdated.range(
            self._last_cached,
            last_block := self.chain_manager.blocks.head.number,
        ):
            if log.enabled:
                self._cached_modules.add(
                    self.chain_manager.contracts.instance_at(log.module)
                )

            else:
                self._cached_modules.remove(log.module)

            self._last_cached = last_block

    def __iter__(self) -> "Iterator[ContractInstance]":
        self._update_cache()
        return iter(self._cached_modules)

    def __contains__(self, address: Any) -> bool:
        return address in self._cached_modules or self.sack.contract.module_enabled(
            address
        )

    def enable(self, module: Any, **txn_args) -> "ReceiptAPI | None":
        if (
            receipt := self.sack.modify(
                ActionType.CONFIGURE_MODULE(
                    self.head,
                    module := self.conversion_manager.convert(module, AddressType),
                    True,
                    version=self.version,
                    address=self.address,
                    chain_id=self.chain_manager.chain_id,
                ),
                **txn_args,
            )
        ) and (
            self.sack.contract.ModuleUpdated(module=module, enabled=True)
            in receipt.events
        ):
            self._cached_modules.add(self.chain_manager.contracts.instance_at(module))

        return receipt

    def disable(self, module: Any, **txn_args) -> "ReceiptAPI | None":
        if (
            receipt := self.sack.modify(
                ActionType.CONFIGURE_MODULE(
                    self.head,
                    module := self.conversion_manager.convert(module, AddressType),
                    False,
                    version=self.version,
                    address=self.address,
                    chain_id=self.chain_manager.chain_id,
                ),
                **txn_args,
            )
        ) and (
            self.sack.contract.ModuleUpdated(module=module, enabled=False)
            in receipt.events
        ):
            self._cached_modules.remove(module)

        return receipt
