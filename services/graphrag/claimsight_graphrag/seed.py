"""Seed Neo4j / memory graph."""

from __future__ import annotations

import logging

from claimsight_graphrag.store import get_store, reset_store

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    reset_store()
    store = get_store()
    store.seed()
    log.info("ClaimSight graph seeded (%s)", store.kind())


if __name__ == "__main__":
    main()
