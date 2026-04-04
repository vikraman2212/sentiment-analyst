"""RedisStreamQueue -- re-exported from agent_sdk.

All backend modules that import RedisStreamQueue, _GROUP_NAME, or
_STREAM_KEY from this file continue to work unchanged.
The canonical definitions live in agent_sdk.providers.queue.redis.
"""

from agent_sdk.providers.queue.redis import (  # noqa: F401
    _GROUP_NAME,
    _STREAM_KEY,
    RedisStreamQueue,
)

__all__ = ["RedisStreamQueue", "_GROUP_NAME", "_STREAM_KEY"]
