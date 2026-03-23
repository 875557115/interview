from mcp.server.fastmcp import FastMCP
import os
import redis

mcp = FastMCP("redis-server")

_redis_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    _redis_client = redis.Redis(host=host, port=port, decode_responses=True)
    print(f"redis_client: {host}:{port}")
    return _redis_client

@mcp.tool()
def redis_get(key: str) -> str:
    """Get value from redis"""
    try:
        value = _get_client().get(key)
        return "" if value is None else value
    except Exception as e:
        return f"redis_get error: {e}"

@mcp.tool()
def redis_set(key: str, value: str) -> str:
    """Set value to redis"""
    try:
        _get_client().set(key, value)
        return "ok"
    except Exception as e:
        return f"redis_set error/: {e}"

if __name__ == "__main__":
    mcp.run()
