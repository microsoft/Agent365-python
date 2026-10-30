# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""HTTP session helper shared by the Defender client and token resolvers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp


@asynccontextmanager
async def http_session(
    session: aiohttp.ClientSession | None,
) -> AsyncIterator[aiohttp.ClientSession]:
    """Yield the caller's session, or a session that is closed when the block exits.

    Args:
        session: A pooled session owned by the caller, or ``None`` for a per-call session.

    Yields:
        The session to send the request with.
    """
    if session is not None:
        yield session
        return

    async with aiohttp.ClientSession() as owned:
        yield owned
