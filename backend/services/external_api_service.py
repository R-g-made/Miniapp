from typing import List, Optional, Dict, Any
from uuid import UUID
from backend.schemas.external_api import (
    ExternalProviderType, 
    FloorPriceUpdate, 
    StickerPurchaseRequest, 
    StickerTransferRequest,
    ExternalApiResult
)
from loguru import logger

from backend.services.thermos_service import thermos_service
from backend.services.getgems_service import getgems_service
from backend.services.laffka_service import laffka_service

class ExternalApiService:
    """
    Сервис для взаимодействия с внешними блокчейн-API и маркетплейсами.
    Инкапсулирует логику работы с разными провайдерами (GetGems, TonAPI и т.д.).
    """

    async def update_floor_price(
        self, 
        updates: List[FloorPriceUpdate], 
        provider: ExternalProviderType = ExternalProviderType.TON_API
    ) -> List[ExternalApiResult]:
        """
        Обновление флор-прайса для одного или нескольких элементов каталога.
        """
        results = []
        for update in updates:
            success = False
            new_price = None
            details = {"catalog_id": str(update.catalog_id)}

            try:
                if provider == ExternalProviderType.GETGEMS:
                    # Нам нужен адрес коллекции из БД (обычно передается в деталях или подгружается)
                    collection_address = update.details.get("collection_address") if update.details else None
                    if collection_address:
                        new_price = await getgems_service.get_floor_price(collection_address)
                        if new_price is not None:
                            success = True
                            details["new_price"] = new_price
                    else:
                        logger.warning(f"ExternalApiService: No collection_address for GetGems update of {update.catalog_id}")

                elif provider == ExternalProviderType.LAFFKA:
                    sticker_id = update.details.get("laffka_sticker_id")
                    collection_address = update.details.get("collection_address")
                    
                    if sticker_id:
                        data = await laffka_service.get_listings(sticker_id=sticker_id, sort="price-low-high")
                        items = data.get("items", [])
                        if items:
                            new_price = float(items[0].get("price", 0)) / 10**9
                            success = True
                            details["new_price"] = new_price
                    elif collection_address:
                        # Фолбэк на флор коллекции
                        new_price = await laffka_service.get_floor_price(collection_address)
                        if new_price is not None:
                            success = True
                            details["new_price"] = new_price

                # Default fallback for TON_API or unimplemented providers
                if not success and provider == ExternalProviderType.TON_API:
                    logger.info(f"Mock: Updating floor price for {update.catalog_id} via {provider}")
                    success = True
                    details["new_price"] = update.new_price_ton or 0.1 # Mock price

                results.append(ExternalApiResult(
                    success=success,
                    provider=provider,
                    details=details,
                    error=None if success else "Failed to fetch price"
                ))
            except Exception as e:
                logger.error(f"ExternalApiService: Error updating floor price for {update.catalog_id}: {e}")
                results.append(ExternalApiResult(
                    success=False,
                    provider=provider,
                    details=details,
                    error=str(e)
                ))

        return results

    async def buy_stickers(
        self, 
        requests: List[StickerPurchaseRequest], 
        db: Any = None,
        provider: ExternalProviderType = ExternalProviderType.GETGEMS
    ) -> List[ExternalApiResult]:
        """
        Покупка одного или нескольких стикеров на внешнем маркетплейсе.
        DISABLED: Функция временно отключена (находится в разработке).
        """
        logger.info(f"ExternalApiService: buy_stickers is currently DISABLED (provider: {provider})")
        return [
            ExternalApiResult(
                success=False,
                provider=provider,
                details={},
                error="Auto-buy is under development and currently disabled"
            ) for _ in requests
        ]

        if provider == ExternalProviderType.LAFFKA and requests and db:
            first_req = requests[0]
            sticker_id = first_req.details.get("laffka_sticker_id")
            catalog_id = first_req.catalog_id
            
            if sticker_id:
                logger.info(f"ExternalApiService: Starting bulk purchase for {sticker_id} via Laffka (count: {len(requests)})")
                purchase_results = await laffka_service.buy_missing_stickers(db, catalog_id, sticker_id, len(requests))
                
                for res in purchase_results:
                    success = "error" not in res
                    results.append(ExternalApiResult(
                        success=success,
                        provider=provider,
                        details=res,
                        error=res.get("error") if not success else None
                    ))
                return results

        if provider == ExternalProviderType.GETGEMS and requests and db:
            first_req = requests[0]
            collection_address = first_req.details.get("collection_address")
            catalog_id = first_req.catalog_id
            
            if collection_address:
                logger.info(f"ExternalApiService: Starting bulk purchase for {collection_address} via GetGems (count: {len(requests)})")
                purchase_results = await getgems_service.buy_missing_stickers(db, catalog_id, collection_address, len(requests))
                
                for res in purchase_results:
                    success = res.get("success", False)
                    results.append(ExternalApiResult(
                        success=success,
                        provider=provider,
                        details=res,
                        error=res.get("error") if not success else None
                    ))
                return results

        for req in requests:
            logger.info(f"Buying sticker via {provider} for {req.max_price} {req.currency}")
            # TODO: Реализовать интеграцию для других провайдеров
            results.append(ExternalApiResult(
                success=True,
                provider=provider,
                details={"status": "pending_tx"}
            ))
        return results

    async def transfer_sticker(
        self, 
        request: StickerTransferRequest, 
        provider: ExternalProviderType = ExternalProviderType.TON_API
    ) -> ExternalApiResult:
        """
        Трансфер (вывод) единичного экземпляра стикера на внешний кошелек.
        """
        logger.info(f"ExternalApiService: Transferring sticker via {provider} to {request.target_address}")
        
        try:
            if provider == ExternalProviderType.GETGEMS:
                # Нам нужен nft_address и цена для роялти из деталей
                nft_address = request.details.get("nft_address")
                price_ton = request.details.get("price_ton")
                
                if not nft_address:
                    raise Exception("nft_address is missing in request details")
                
                tx_hash = await getgems_service.transfer_nft(
                    nft_address=nft_address, 
                    destination_address=request.target_address,
                    price_ton=price_ton
                )
                
                if tx_hash:
                    return ExternalApiResult(
                        success=True,
                        provider=provider,
                        details={"tx_hash": tx_hash}
                    )
                else:
                    return ExternalApiResult(
                        success=False,
                        provider=provider,
                        error="Blockchain transfer failed"
                    )
            
            elif provider == ExternalProviderType.LAFFKA:
                is_onchain = request.details.get("is_onchain", False)
                sticker_uuid = request.details.get("nft_address")
                
                if not sticker_uuid:
                    raise Exception("Laffka sticker UUID is missing in details")
                
                if is_onchain:
                    success = await laffka_service.withdraw_nft(sticker_uuid, request.target_address)
                else:
                    success = await laffka_service.withdraw_sticker(sticker_uuid)
                
                if success:
                    return ExternalApiResult(
                        success=True,
                        provider=provider,
                        details={"tx_hash": f"laffka_{sticker_uuid}"}
                    )
                else:
                    return ExternalApiResult(
                        success=False,
                        provider=provider,
                        error="Laffka withdrawal failed"
                    )

            logger.info(f"Mock: Transferring sticker via {provider}")
            return ExternalApiResult(
                success=True,
                provider=provider,
                details={"tx_hash": "tx_mocked_hash"}
            )
        except Exception as e:
            logger.error(f"ExternalApiService: Error during transfer: {e}")
            return ExternalApiResult(
                success=False,
                provider=provider,
                error=str(e)
            )

external_api_service = ExternalApiService()