"""Reusable consumer boundaries: return verified synthetic input, never execute.

No legacy callbacks, database restore, dispatch, PnL calculation or I/O exists.
Every entrypoint requires freshly scoped receipts through the common selector.
"""
from .authority import AuthoritySelector, Denied, read_archive


class ConsumerAdapters:
    def __init__(self, selector):
        if type(selector) is not AuthoritySelector:
            raise Denied('SHARED_SELECTOR_REQUIRED')
        self.selector = selector

    def restore(self, evidence, intent):
        return self.selector.select(evidence, 'restore', intent)

    def worker(self, evidence, intent):
        return self.selector.select(evidence, 'worker', intent)

    def handoff(self, evidence, intent):
        return self.selector.select(evidence, 'handoff', intent)

    def economic(self, evidence, intent):
        return self.selector.select(evidence, 'economic', intent)

    @staticmethod
    def archive(raw, trusted_pin):
        return read_archive(raw, trusted_pin)
