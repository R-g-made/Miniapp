import asyncio
import sys
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем корневую директорию проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.laffka_service import laffka_service
from loguru import logger
from httpx import Response, HTTPStatusError

async def test_laffka_full_cycle():
    logger.info("Starting Laffka Full Cycle Test (Mocked)...")
    
    # 1. Данные для теста
    catalog_id = uuid.uuid4()
    laffka_sticker_id = "coll1:stick1"
    needed_count = 1
    
    # 2. Мокаем базу данных
    db = AsyncMock()
    
    # 3. Мокаем CRUD операции
    with patch("app.crud.sticker.sticker.update_catalog_floor_price", new_callable=AsyncMock) as mock_update_price, \
         patch("app.crud.sticker.sticker.create", new_callable=AsyncMock) as mock_create_sticker:
        
        # 4. Мокаем HTTP запросы Laffka API
        # Мы переопределяем _request напрямую в инстансе laffka_service для простоты теста
        original_request = laffka_service._request
        
        async def mock_request(method, endpoint, **kwargs):
            logger.debug(f"Mock Request: {method} {endpoint}")
            
            # Ответ для получения листингов
            if method == "GET" and "api/v1/market/listings" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "items": [
                            {
                                "id": "listing_123",
                                "sticker_id": laffka_sticker_id,
                                "price": "1000000000", # 1 TON
                                "serial_number": 42
                            }
                        ],
                        "next_cursor": None
                    },
                    raise_for_status=lambda: None
                )
            
            # Ответ для покупки
            if method == "POST" and "api/v1/market/purchase/listing_123" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "id": "sticker_uuid_abc",
                        "sticker_id": laffka_sticker_id,
                        "price": "1000000000",
                        "serial_number": 42,
                        "status": "SOLD"
                    },
                    raise_for_status=lambda: None
                )
            
            # Ответ для вывода (withdraw)
            if method == "POST" and "api/v1/sp/withdraw" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {"ok": True},
                    raise_for_status=lambda: None
                )
            
            return MagicMock(status_code=404, raise_for_status=lambda: None)

        # Заменяем _request на наш мок
        laffka_service._request = mock_request
        
        try:
            # 5. Запуск полного цикла
            logger.info(f"Running buy_missing_stickers for catalog {catalog_id}...")
            results = await laffka_service.buy_missing_stickers(
                db=db,
                catalog_id=catalog_id,
                laffka_sticker_id=laffka_sticker_id,
                needed_count=needed_count
            )
            
            # 6. Проверка результатов
            logger.info("Verifying results...")
            
            # Проверяем, что вернулся результат покупки
            assert len(results) == 1
            assert results[0]["id"] == "sticker_uuid_abc"
            logger.success("Purchase result verified.")
            
            # Проверяем вызовы CRUD
            mock_update_price.assert_called_once()
            logger.success("CRUD update_catalog_floor_price called.")
            
            mock_create_sticker.assert_called_once()
            # Проверяем, что в БД сохранился правильный nft_address (uuid покупки)
            args, kwargs = mock_create_sticker.call_args
            assert kwargs["obj_in"]["nft_address"] == "sticker_uuid_abc"
            assert kwargs["obj_in"]["number"] == 42
            logger.success("CRUD create (UserSticker) verified.")
            
            # Проверяем коммит
            assert db.commit.called
            logger.success("Database commit called.")
            
            logger.success("FULL CYCLE TEST PASSED!")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
            raise e
        finally:
            # Восстанавливаем оригинальный метод
            laffka_service._request = original_request

if __name__ == "__main__":
    asyncio.run(test_laffka_full_cycle())
