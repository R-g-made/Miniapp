import asyncio
import httpx
import json
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.config import settings

async def test_getgems_slon_direct():
    """
    Тест GetGems: Прямой запрос с API Key в заголовке Authorization.
    Как в curl: -H 'Authorization: <API KEY>'
    """
    collection_address = "EQAqAMKN5XGbLcf6JAfJWuCsjCyy4_MDqQ_Fo216GhjnpT08"
    api_token = settings.GETGEMS_API_TOKEN
    
    print(f"--- GetGems Direct API Key Test ---")
    if not api_token:
        print("ERROR: GETGEMS_API_TOKEN not found in .env")
        return

    # Эндпоинт из твоего примера
    url = f"https://api.getgems.io/public-api/v1/nfts/on-sale/{collection_address}"
    print(f"URL: {url}")
    print(f"Using Authorization: {api_token[:10]}...")

    headers = {
        "accept": "application/json",
        "Authorization": api_token,
        "User-Agent": "PostmanRuntime/7.32.3" # Оставляем для обхода CloudFront
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(url, headers=headers, params={"limit": 5})
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print("\n[SUCCESS] Data received!")
                print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            else:
                print(f"Failed: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_getgems_slon_direct())