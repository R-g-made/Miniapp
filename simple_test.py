import asyncio
from backend.core.config import settings
from tonutils.clients import TonapiClient

async def test():
    client = TonapiClient(api_key=settings.TON_API_KEY, network='mainnet', base_url='https://tonapi.io/v2')
    await client.connect()
    try:
        info = await client.get_info('UQBiKevgEcPjgDo0JxTvodoutF8YVD9Lu8AcuJ0CnuWldL31')
        print(f"Balance: {info.balance}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test())
