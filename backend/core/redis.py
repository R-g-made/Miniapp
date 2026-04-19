from typing import Optional, Dict, List, Any
from backend.core.config import settings

class RedisServiceMock:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lists: Dict[str, List[str]] = {}

    async def connect(self):
        return self

    async def disconnect(self):
        pass

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, expire: int = None):
        self._data[key] = value

    async def lpush(self, key: str, value: str):
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].insert(0, value)

    async def ltrim(self, key: str, start: int, end: int):
        if key in self._lists:
            self._lists[key] = self._lists[key][start:end+1]

    async def lrange(self, key: str, start: int, end: int):
        if key not in self._lists:
            return []
        if end == -1:
            return self._lists[key][start:]
        return self._lists[key][start:end+1]

if settings.USE_REDIS:
    import redis.asyncio as redis
    class RedisServiceReal:
        def __init__(self, url: str):
            self.url = url
            self._client = None

        async def connect(self):
            if not self._client:
                self._client = redis.from_url(self.url, decode_responses=True)
            return self._client

        async def disconnect(self):
            if self._client:
                await self._client.close()
                self._client = None

        async def get(self, key: str):
            client = await self.connect()
            return await client.get(key)

        async def set(self, key: str, value: str, expire: int = None):
            client = await self.connect()
            await client.set(key, value, ex=expire)

        async def lpush(self, key: str, value: str):
            client = await self.connect()
            await client.lpush(key, value)

        async def ltrim(self, key: str, start: int, end: int):
            client = await self.connect()
            await client.ltrim(key, start, end)

        async def lrange(self, key: str, start: int, end: int):
            client = await self.connect()
            return await client.lrange(key, start, end)

    redis_service = RedisServiceReal(url=settings.redis_connection_url)
else:
    redis_service = RedisServiceMock()

async def get_redis():
    return await redis_service.connect()
