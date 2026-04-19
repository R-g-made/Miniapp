import asyncio
import sys
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем корневую директорию проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Мокаем TonapiClient ДО импорта сервиса, чтобы избежать ошибки инициализации
with patch("tonutils.clients.TonapiClient"):
    from app.services.getgems_service import getgems_service

from loguru import logger

async def test_gg_full_cycle():
    logger.info("Starting GetGems (GG) Full Cycle Test (Mocked)...")
    
    # 1. Данные для теста
    catalog_id = uuid.uuid4()
    collection_address = "EQD_COLLECTION_ADDRESS_123"
    needed_count = 1
    nft_address = "EQB_NFT_ITEM_ADDRESS_ABC"
    
    # 2. Мокаем базу данных
    db = AsyncMock()
    
    # 3. Мокаем CRUD операции
    with patch("app.crud.sticker.sticker.update_catalog_floor_price", new_callable=AsyncMock) as mock_update_price, \
         patch("app.crud.sticker.sticker.create", new_callable=AsyncMock) as mock_create_sticker:
        
        # 4. Мокаем методы сервиса
        # Мокаем _request для API вызовов GetGems
        original_request = getgems_service._request
        
        async def mock_request(method, endpoint, **kwargs):
            logger.debug(f"Mock GG Request: {method} {endpoint}")
            
            # Ответ для получения листингов (on-sale)
            if method == "GET" and f"v1/nfts/on-sale/{collection_address}" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "items": [
                            {
                                "address": nft_address,
                                "price": "1500000000", # 1.5 TON
                                "index": 777
                            }
                        ]
                    },
                    raise_for_status=lambda: None
                )
            
            # Ответ для параметров покупки (buy-fix-price)
            if method == "POST" and f"v1/nfts/buy-fix-price/{nft_address}" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "to": "EQ_MARKETPLACE_CONTRACT",
                        "amount": "1500000000",
                        "payload": "te6ccgEBAQEAMAAAW1..."
                    },
                    raise_for_status=lambda: None
                )
            
            return MagicMock(status_code=404, raise_for_status=lambda: None)

        # Подменяем методы в инстансе
        getgems_service._request = mock_request
        
        # Мокаем реальные блокчейн-действия
        with patch.object(getgems_service, "execute_ton_transfer", new_callable=AsyncMock) as mock_transfer, \
             patch.object(getgems_service, "verify_nft_ownership", new_callable=AsyncMock) as mock_verify:
            
            mock_transfer.return_value = "fake_tx_hash_0x123"
            mock_verify.return_value = True
            
            try:
                # 5. Запуск полного цикла
                logger.info(f"Running buy_missing_stickers for catalog {catalog_id} via GetGems...")
                results = await getgems_service.buy_missing_stickers(
                    db=db,
                    catalog_id=catalog_id,
                    collection_address=collection_address,
                    needed_count=needed_count
                )
                
                # 6. Проверка результатов
                logger.info("Verifying GG results...")
                
                # Проверяем, что вернулся успех
                assert len(results) == 1
                assert results[0]["success"] is True
                assert results[0]["nft_address"] == nft_address
                assert results[0]["tx_hash"] == "fake_tx_hash_0x123"
                logger.success("GG Purchase result verified.")
                
                # Проверяем вызовы CRUD
                mock_update_price.assert_called_once()
                # Проверяем цену (1.5 TON)
                args, kwargs = mock_update_price.call_args
                assert kwargs["ton_price"] == 1.5
                logger.success("CRUD update_catalog_floor_price verified with price 1.5 TON.")
                
                mock_create_sticker.assert_called_once()
                args, kwargs = mock_create_sticker.call_args
                assert kwargs["obj_in"]["nft_address"] == nft_address
                assert kwargs["obj_in"]["number"] == 777
                logger.success("CRUD create (UserSticker) verified with correct NFT data.")
                
                # Проверяем коммит
                assert db.commit.called
                logger.success("Database commit called.")
                
                logger.success("GETGEMS FULL CYCLE TEST PASSED!")
                
            except Exception as e:
                logger.error(f"GG Test failed: {e}")
                import traceback
                traceback.print_exc()
                raise e
            finally:
                # Восстанавливаем оригинальный метод
                getgems_service._request = original_request

if __name__ == "__main__":
    asyncio.run(test_gg_full_cycle())
