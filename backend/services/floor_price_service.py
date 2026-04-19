import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from loguru import logger
from typing import Dict, Any, Optional, Tuple
from backend.models.sticker import LaffkaMapping
from sqlalchemy import select
from backend.services.external_api_service import external_api_service
from backend.schemas.external_api import FloorPriceUpdate, ExternalProviderType
from backend.core.config import settings
from backend.crud.sticker import sticker as crud_sticker
from backend.crud.case import case as crud_case
from backend.services.chance_service import chance_service

class FloorPriceService:
    """Сервис для синхронизации флор-прайсов с внешними маркетплейсами"""
    
    @property
    def api_url(self) -> str:
        return settings.STICKERS_TOOLS_API_URL

    async def _fetch_all_floors_from_tools(self) -> Dict[str, Dict[str, float]]:
        """
        Получает все флор-прайсы с stickers.tools по логике из allfloors.py
        """
        headers = {
            "User-Agent": "sticker-floor-bot/2.0",
            "Accept": "application/json",
            "Referer": "https://stickers.tools/",
            "Origin": "https://stickers.tools",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(self.api_url, headers=headers)
                response.raise_for_status()
                payload = response.json()
                
                collections = payload.get("collections", {})
                if not isinstance(collections, dict):
                    return {}

                all_floors = {}
                for col in collections.values():
                    cname = col.get("name")
                    if not cname: continue
                    
                    stickers = col.get("stickers") or {}
                    for pack in stickers.values():
                        pname = pack.get("name")
                        if not pname: continue
                        
                        ton_floor = self._get_pack_floor_ton(pack)
                        if ton_floor:
                            if cname not in all_floors:
                                all_floors[cname] = {}
                            all_floors[cname][pname] = ton_floor
                
                return all_floors
            except Exception as e:
                logger.error(f"FloorPriceService: Failed to fetch floors from tools: {e}")
                return {}

    def _get_pack_floor_ton(self, pack: Dict[str, Any]) -> Optional[float]:
        """Приоритет: current -> 24h -> 7d -> 30d"""
        prio_ton = [
            ["current", "price", "floor", "ton"],
            ["24h", "price", "floor", "ton"],
            ["7d", "price", "floor", "ton"],
            ["30d", "price", "floor", "ton"],
        ]
        
        for path in prio_ton:
            val = pack
            for key in path:
                if isinstance(val, dict) and key in val:
                    val = val[key]
                else:
                    val = None
                    break
            if val is not None:
                try:
                    return float(val)
                except:
                    continue
        return None

    def _should_update_price(self, old_price: Optional[float], new_price: float) -> bool:
        """
        Проверяет, нужно ли обновлять цену на основе 20% порога (если настроен)
        """
        if old_price is None or old_price == 0:
            return True # Всегда обновляем, если старой цены нет
            
        threshold = settings.MAX_FLOOR_PRICE_CHANGE_PERCENTAGE
        if threshold is None:
            return True # Порог не задан - обновляем всегда
            
        diff_percent = abs(new_price - old_price) / old_price
        return diff_percent >= threshold

    async def update_all_prices(self, db: AsyncSession):
        """Обновляет цены для всего каталога на основе данных из TON API/GetGems/Laffka/StickersTools"""
        logger.info("FloorPriceService: Syncing floor prices...")
        
        # 1. Получаем все каталоги
        catalogs = await crud_sticker.get_all_catalogs(db)
        
        # 2. Получаем данные со stickers.tools (основной источник флоров)
        tools_floors = await self._fetch_all_floors_from_tools()
        
        for catalog in catalogs:
            new_price_ton = None
            
            # 3. Пытаемся найти флор в tools_floors (по коллекции и имени)
            col_name = catalog.collection_name
            pack_name = catalog.name
            
            if col_name in tools_floors and pack_name in tools_floors[col_name]:
                new_price_ton = tools_floors[col_name][pack_name]
                logger.debug(f"FloorPriceService: Found price for {pack_name} in stickers.tools: {new_price_ton} TON")
            
            # 4. Если в tools нет, используем провайдеров (GetGems/Laffka) - DISABLED
            # if new_price_ton is None:
            #     provider = ExternalProviderType.GETGEMS if catalog.is_onchain else ExternalProviderType.LAFFKA
            #     logger.info(f"FloorPriceService: {catalog.name} not found in tools, falling back to {provider}")
            #     
            #     details = {"collection_address": catalog.collection_address}
            #     if provider == ExternalProviderType.LAFFKA:
            #         mapping_stmt = select(LaffkaMapping).where(LaffkaMapping.catalog_id == catalog.id)
            #         mapping_res = await db.execute(mapping_stmt)
            #         mapping = mapping_res.scalar_one_or_none()
            #         if mapping:
            #             details["laffka_sticker_id"] = mapping.laffka_sticker_id
            #
            #     update_req = FloorPriceUpdate(
            #         catalog_id=catalog.id,
            #         details=details
            #     )
            #     results = await external_api_service.update_floor_price([update_req], provider=provider)
            #     for res in results:
            #         if res.success and "new_price" in res.details:
            #             new_price_ton = res.details["new_price"]
            
            # 5. Применяем логику 20% порога
            if new_price_ton is not None:
                if self._should_update_price(catalog.floor_price_ton, new_price_ton):
                    logger.info(f"FloorPriceService: Updating price for {catalog.name}: {catalog.floor_price_ton} -> {new_price_ton}")
                    await self._update_catalog_price(db, catalog.id, new_price_ton)
                else:
                    logger.debug(f"FloorPriceService: Price change for {catalog.name} below threshold, skipping ({catalog.floor_price_ton} -> {new_price_ton})")
            else:
                logger.warning(f"FloorPriceService: No floor price found for {catalog.name}, keeping old value.")
                
        await db.commit()
        
        # 6. После обновления всех цен, пересчитываем шансы и цены для всех активных кейсов
        # Это гарантирует соблюдение RTP 90% при изменении рыночных цен
        logger.info("FloorPriceService: Rebalancing case chances and prices...")
        active_cases = await crud_case.get_catalog(db, only_active=True)
        for case_obj in active_cases:
            await chance_service.recalculate_case_chances(db, case_obj.id)
            
        logger.info("FloorPriceService: Prices synced and cases rebalanced successfully.")

    async def _update_catalog_price(self, db: AsyncSession, catalog_id: UUID, new_price_ton: float):
        """Вспомогательный метод для обновления цены в БД"""
        await crud_sticker.update_catalog_floor_price(
            db, 
            catalog_id=catalog_id, 
            ton_price=new_price_ton,
            stars_price=new_price_ton / settings.STARS_TO_TON_RATE
        )

floor_price_service = FloorPriceService()