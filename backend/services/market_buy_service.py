from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import uuid
from loguru import logger
from backend.models.sticker import LaffkaMapping, PriorityMarket
from sqlalchemy import select
from backend.services.external_api_service import external_api_service
from backend.services.chance_service import chance_service
from backend.schemas.external_api import StickerPurchaseRequest, ExternalProviderType
from backend.core.config import settings
from backend.crud.sticker import sticker as crud_sticker

class MarketBuyService:
    """Сервис для автоматической покупки стикеров на маркетплейсах"""
    
    async def run_auto_buy(self, db: AsyncSession):
        """Проверяет остатки в пуле и докупает стикеры, если их мало"""
        logger.info("MarketBuyService: Auto-buy is currently DISABLED (under development).")
        return
        
        # 1. Получаем все элементы каталога
        catalogs = await crud_sticker.get_all_catalogs(db)
        
        for catalog in catalogs:
            # 2. Считаем, сколько таких стикеров сейчас доступно в системе
            available_count = await crud_sticker.count_available_in_pool(db, catalog.id)
            
            # Лимит из модели или 5 по умолчанию. Если 0 — не докупать!
            pool_limit = catalog.max_pool_size
            if pool_limit == 0:
                logger.info(f"MarketBuyService: Auto-buy disabled for {catalog.name} (max_pool_size = 0), skipping.")
                continue
            if pool_limit is None:
                pool_limit = 5
            
            # Если в пуле меньше нужного количества — нужно докупить
            if available_count < pool_limit:
                needed = pool_limit - available_count
                logger.info(f"MarketBuyService: Low stock for {catalog.name}: {available_count}/{pool_limit}. Buying {needed} more...")
                
                # 3. Определяем провайдера на основе приоритетного маркета в каталоге
                provider_map = {
                    PriorityMarket.LAFFKA: ExternalProviderType.LAFFKA,
                    PriorityMarket.GETGEMS: ExternalProviderType.GETGEMS,
                    PriorityMarket.THERMOS: ExternalProviderType.THERMOS,
                }
                provider = provider_map.get(catalog.priority_market, ExternalProviderType.LAFFKA)
                
                details = {"collection_address": catalog.collection_address}
                
                # Если Laffka — ищем маппинг
                if provider == ExternalProviderType.LAFFKA:
                    mapping_stmt = select(LaffkaMapping).where(LaffkaMapping.catalog_id == catalog.id)
                    mapping_res = await db.execute(mapping_stmt)
                    mapping = mapping_res.scalar_one_or_none()
                    if mapping:
                        details["laffka_sticker_id"] = mapping.laffka_sticker_id
                    else:
                        logger.warning(f"MarketBuyService: No Laffka mapping for {catalog.name}, skip.")
                        continue

                # 4. Формируем запрос на покупку
                purchase_price = catalog.floor_price_ton * 1.1 if catalog.floor_price_ton else 1.5
                purchase_req = StickerPurchaseRequest(
                    catalog_id=catalog.id,
                    max_price=purchase_price,
                    currency="ton",
                    details=details
                )
                
                # 5. Вызываем внешний API
                results = await external_api_service.buy_stickers([purchase_req for _ in range(needed)], db=db, provider=provider)
                
                # В LaffkaService и GetGemsService покупка уже создает UserSticker в БД
                # Здесь обрабатываем только если другие провайдеры (моки и т.д.)
                if provider not in [ExternalProviderType.LAFFKA, ExternalProviderType.GETGEMS]:
                    for res in results:
                        if res.success:
                            # 6. Добавляем купленный NFT в пул (Mock)
                            await crud_sticker.create(db, obj_in={
                                "catalog_id": catalog.id,
                                "owner_id": None,
                                "is_available": True,
                                "number": available_count + 1,
                                "nft_address": f"EQ_MOCKED_{uuid.uuid4().hex[:8]}"
                            })
                            available_count += 1
                            
                            # 7. Обновляем цену флора на цену покупки
                            await crud_sticker.update_catalog_floor_price(
                                db, 
                                catalog_id=catalog.id, 
                                ton_price=purchase_price,
                                stars_price=purchase_price / settings.STARS_TO_TON_RATE
                            )

                # 8. После пополнения пула пересчитываем шансы во всех кейсах, где есть этот стикер
                # Это гарантирует RTP 90% при изменении запасов
                from backend.models.case import Case
                stmt_cases = select(Case).join(CaseItem).where(CaseItem.sticker_catalog_id == catalog.id)
                res_cases = await db.execute(stmt_cases)
                for case_obj in res_cases.scalars().all():
                    await chance_service.recalculate_case_chances(db, case_obj.id)
                        
        await db.commit()
        logger.info("MarketBuyService: Auto-buy process finished.")

market_buy_service = MarketBuyService()