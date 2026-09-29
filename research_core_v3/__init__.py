"""Minimal deterministic Research Core V3.

AI chooses/finalizes experiment specs outside the inner loop. This package executes
frozen specs deterministically and never calls an AI/provider or mutates GitHub.
"""
__all__ = ["engine", "model", "signals", "inventory", "migration"]
