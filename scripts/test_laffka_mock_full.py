import asyncio
import sys
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем корневую директорию проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Мокаем TonapiClient ДО импорта сервиса
with patch("tonutils.clients.TonapiClient"):
    from app.services.laffka_service import laffka_service

from loguru import logger
from httpx import Response, HTTPStatusError

async def test_laffka_full_cycle_mocked():
    logger.info("Starting Laffka Full Cycle Mocked Test (On-chain & Off-chain)...")
    
    # 1. Данные для теста
    catalog_id = uuid.uuid4()
    laffka_sticker_id = "coll1:stick1"
    needed_count = 2 # Один оффчейн, один ончейн
    
    # 2. Мокаем базу данных и зависимости
    db = AsyncMock()
    
    # Мокаем StickerCatalog для получения collection_address
    mock_catalog = MagicMock()
    mock_catalog.id = catalog_id
    mock_catalog.collection_address = "EQ_COLLECTION_123"
    
    # Мокаем выполнение запроса в БД
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_catalog
    db.execute.return_value = mock_execute_result
    
    # 3. Мокаем CRUD операции
    with patch("app.crud.sticker.sticker.update_catalog_floor_price", new_callable=AsyncMock) as mock_update_price, \
         patch("app.crud.sticker.sticker.create", new_callable=AsyncMock) as mock_create_sticker:
        
        # 4. Мокаем HTTP запросы Laffka API
        original_request = laffka_service._request
        
        async def mock_request(method, endpoint, **kwargs):
            logger.debug(f"Mock Request: {method} {endpoint}")
            
            # Ответ для получения листингов (2 штуки)
            if method == "GET" and "api/v1/market/listings" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "items": [
                            {"id": "listing_offchain", "sticker_id": laffka_sticker_id, "price": "1000000000", "serial_number": 1},
                            {"id": "listing_onchain", "sticker_id": laffka_sticker_id, "price": "2000000000", "serial_number": 2}
                        ],
                        "next_cursor": None
                    },
                    raise_for_status=lambda: None
                )
            
            # Ответ для покупки (оффчейн)
            if method == "POST" and "purchase/listing_offchain" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "id": "offchain_purchase_id",
                        "price": "1000000000",
                        "serial_number": 1,
                        "sticker": {"id": "sticker_uuid_offchain", "sticker_type": "offchain"}
                    },
                    raise_for_status=lambda: None
                )
            
            # Ответ для покупки (ончейн)
            if method == "POST" and "purchase/listing_onchain" in endpoint:
                return MagicMock(
                    status_code=200,
                    json=lambda: {
                        "id": "onchain_purchase_id",
                        "price": "2000000000",
                        "serial_number": 2,
                        "sticker": {"id": "sticker_uuid_onchain", "sticker_type": "onchain"}
                    },
                    raise_for_status=lambda: None
                )
            
            # Ответ для вывода стикерпака
            if method == "POST" and "api/v1/sp/withdraw" in endpoint:
                return MagicMock(status_code=200, json=lambda: {"ok": True}, raise_for_status=lambda: None)
            
            # Ответ для вывода NFT
            if method == "POST" and "api/v1/users/withdraw-nft" in endpoint:
                return MagicMock(status_code=200, json=lambda: {"ok": True}, raise_for_status=lambda: None)
            
            return MagicMock(status_code=404, raise_for_status=lambda: None)

        # Заменяем _request
        laffka_service._request = mock_request
        
        # Мокаем проверку блокчейна (приход NFT)
        # Мы просто замокаем метод verify_nft_arrival в инстансе
        with patch.object(laffka_service, "verify_nft_arrival", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = "EQ_NEW_NFT_ADDRESS_456"
            
            try:
                # 5. Запуск процесса
                results = await laffka_service.buy_missing_stickers(
                    db=db,
                    catalog_id=catalog_id,
                    laffka_sticker_id=laffka_sticker_id,
                    needed_count=needed_count
                )
                
                # 6. Проверки
                logger.info("Verifying mock test results...")
                
                assert len(results) == 2
                logger.success("Purchased 2 stickers.")
                
                # Проверяем вызовы создания в БД
                assert mock_create_sticker.call_count == 2
                
                # Первый (оффчейн)
                call_off = mock_create_sticker.call_args_list[0]
                assert call_off.kwargs["obj_in"]["is_onchain"] is False
                assert call_off.kwargs["obj_in"]["nft_address"] == "offchain_purchase_id"
                logger.success("Off-chain instance verified in DB.")
                
                # Второй (ончейн)
                call_on = mock_create_sticker.call_args_list[1]
                assert call_on.kwargs["obj_in"]["is_onchain"] is True
                assert call_on.kwargs["obj_in"]["nft_address"] == "EQ_NEW_NFT_ADDRESS_456"
                logger.success("On-chain instance verified in DB with blockchain address.")
                
                # Проверяем обновление цены (последним был ончейн за 2 TON)
                mock_update_price.assert_called()
                last_price_call = mock_update_price.call_args_list[-1]
                assert last_price_call.kwargs["ton_price"] == 2.0
                logger.success("Floor price updates verified.")
                
                logger.success("✅ MOCKED FULL CYCLE TEST PASSED!")
                
            finally:
                laffka_service._request = original_request

if __name__ == "__main__":
    asyncio.run(test_laffka_full_cycle_mocked())
