"""RedisStreamQueue -- re-exported from agent_sdk.

All backend modules that import RedisStreamQueue or the default stream key
/ group name constants continue to work via these aliased re-exports.
The canonical definitions live in agent_sdk.providers.queue.redis.
"""

from agent_sdk.providers.queue.redis import (  # noqa: F401
    _DEFAULT_GROUP_NAME as _GROUP_NAME,
    _DEFAULT_STREAM_KEY as _STREAM_KEY,
    RedisStreamQueue,
)

__all__ = ["RedisStreamQueue", "_GROUP_NAME", "_STREAM_KEY"]
