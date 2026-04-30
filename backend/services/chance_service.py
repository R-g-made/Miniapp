from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from loguru import logger
import uuid
import random
import math
from typing import List, Dict, Any, Tuple, Optional

from backend.models.case import Case
from backend.models.associations import CaseItem
from backend.models.sticker import StickerCatalog
from backend.models.enums import WSMessageType
from backend.crud.sticker import sticker as crud_sticker
from backend.core.config import settings

class ChanceService:
    """Сервис для динамического перерасчета шансов в кейсах с поддержкой RTP 90%"""

    @property
    def target_rtp(self) -> float:
        return settings.TARGET_RTP

    @property
    def base_fee(self) -> float:
        return settings.CHANCE_BASE_FEE

    @property
    def fee_tolerance(self) -> float:
        return settings.CHANCE_FEE_TOLERANCE

    @property
    def cheap_threshold(self) -> float:
        return settings.CHANCE_CHEAP_THRESHOLD

    @property
    def expensive_threshold(self) -> float:
        return settings.CHANCE_EXPENSIVE_THRESHOLD

    @property
    def category_limits(self) -> dict:
        return settings.CHANCE_CATEGORY_LIMITS

    async def recalculate_case_chances(self, db: AsyncSession, case_id: uuid.UUID):
        """
        Пересчитывает шансы для кейса и его цену для поддержания 90% RTP.
        Учитывает наличие стикеров в пуле и их текущую рыночную стоимость.
        """
        stmt = (
            select(Case)
            .options(selectinload(Case.items).selectinload(CaseItem.sticker_catalog))
            .where(Case.id == case_id)
        )
        result = await db.execute(stmt)
        case_obj = result.scalar_one_or_none()

        if not case_obj:
            return

        # Если динамическое распределение выключено, мы НЕ трогаем шансы (оставляем из сида),
        # но ОБЯЗАТЕЛЬНО обновляем цену кейса на основе текущего флора.
        if not case_obj.is_chance_distribution:
            await self._update_case_price_only(db, case_obj)
            return

        logger.info(f"ChanceService: Starting smart rebalance for case {case_obj.slug} (RTP {self.target_rtp*100}%)")

        items_data = []
        available_items = []
        
        for item in case_obj.items:
            count = await crud_sticker.count_available_in_pool(db, item.sticker_catalog_id)
            price = item.sticker_catalog.floor_price_ton or 0.1 # Дефолтная цена если нет флора
            
            item_info = {
                "item_obj": item,
                "price": price,
                "is_available": count > 0,
                "id": item.id
            }
            items_data.append(item_info)
            if count > 0:
                available_items.append(item_info)

        if not available_items:
            logger.error(f"ChanceService: No available items in pool for case {case_obj.slug}")
            # Если вообще ничего нет, обнуляем все шансы
            for item in case_obj.items:
                item.chance = 0.0
            await db.commit()
            return

        # Важно: сначала обнуляем шансы у ВСЕХ, кто недоступен
        for item_info in items_data:
            if not item_info["is_available"]:
                item_info["item_obj"].chance = 0.0

        prices = [it["price"] for it in available_items]
        min_p, max_p = min(prices), max(prices)
        p_range = max_p - min_p if max_p > min_p else 1.0
        
        for it in available_items:
            rel_pos = (it["price"] - min_p) / p_range
            
            if rel_pos <= self.cheap_threshold:
                it["category"] = "cheap"
            elif rel_pos >= self.expensive_threshold:
                it["category"] = "expensive"
            else:
                it["category"] = "medium"

        current_case_price = case_obj.price_ton
        if current_case_price <= 0:
            # Округление цены TON вверх до 2 знаков
            current_case_price = math.ceil((sum(prices) / len(prices)) * 1.1 * 100) / 100

        best_chances, final_ev, final_price = await self._run_rebalance_loop(
            available_items, current_case_price
        )

        # Округление шансов до 4 знаков (соответствует 2 знакам после запятой в процентах).
        # Чтобы сумма была ровно 1.0, корректируем последний элемент.
        rounded_chances = [round(c, 4) for c in best_chances]
        if rounded_chances:
            diff = 1.0 - sum(rounded_chances)
            rounded_chances[-1] = round(rounded_chances[-1] + diff, 4)

        for it, chance in zip(available_items, rounded_chances):
            it["item_obj"].chance = chance

        if abs(case_obj.price_ton - final_price) > 0.001:
            logger.info(f"ChanceService: Updating case price {case_obj.slug}: {case_obj.price_ton} -> {final_price} TON")
            case_obj.price_ton = final_price
            case_obj.price_stars = round(final_price / settings.STARS_TO_TON_RATE)

        await db.commit()
        
        # WS broadcast for case status/price update
        from backend.core.websocket_manager import manager
        from backend.schemas.websocket import WSEventMessage
        await manager.broadcast(WSEventMessage(
            type=WSMessageType.CASE_STATUS_UPDATE,
            data={
                "case_slug": case_obj.slug,
                "is_active": case_obj.is_active,
                "price_ton": case_obj.price_ton,
                "price_stars": case_obj.price_stars,
                "rebalanced": True
            }
        ))
        
        logger.info(f"ChanceService: Smart rebalance finished for {case_obj.slug}. Final EV: {final_ev:.4f} TON")

    async def _run_rebalance_loop(
        self, 
        available_items: List[Dict], 
        initial_price: float
    ) -> Tuple[List[float], float, float]:
        """Основной цикл балансировки (адаптация Chanse_git.py)"""
        prices = [it["price"] for it in available_items]
        categories = [it["category"] for it in available_items]
        # Обеспечиваем округление цены TON вверх до 2 знаков
        case_price = math.ceil(initial_price * 100) / 100
        
        best_chances = []
        best_ev = 0.0

        for _ in range(50): # Увеличили количество итераций до 50
            chances = self._compute_initial_chances(available_items)
            target_ev = case_price * self.target_rtp
            
            chances, ev = self._greedy_adjust(prices, chances, categories, target_ev)
            best_chances, best_ev = chances, ev
            
            current_fee = (case_price - ev) / case_price * 100
            tolerance = self.base_fee * (self.fee_tolerance / 100)
            
            if self.base_fee - tolerance <= current_fee <= self.base_fee + tolerance:
                return chances, ev, case_price
            
            # Если не попали, корректируем цену кейса
            price_min = ev / (1 - (self.base_fee + self.fee_tolerance) / 100)
            price_max = ev / (1 - (self.base_fee - self.fee_tolerance) / 100)
            avg_price = (price_min + price_max) / 2
            case_price = math.ceil(avg_price * 100) / 100

        return best_chances, best_ev, case_price

    def _compute_initial_chances(self, available_items: List[Dict]) -> List[float]:
        """Первичное распределение на основе весов категорий"""
        categories = [it["category"] for it in available_items]
        
        # Считаем суммарный вес
        total_weight = sum(self.category_limits[cat]["weight"] for cat in categories) or 1.0
        
        p = []
        for cat in categories:
            # Начальный шанс пропорционален весу категории
            base_share = self.category_limits[cat]["weight"] / total_weight
            # Ограничиваем лимитами категории
            clamped = max(self.category_limits[cat]["min"], min(base_share, self.category_limits[cat]["max"]))
            p.append(clamped)
            
        # Нормализация к 1.0 с сохранением лимитов
        return self._normalize_with_limits(p, categories)

    def _normalize_with_limits(self, chances: List[float], categories: List[str]) -> List[float]:
        """Нормализация суммы шансов к 1.0 с учетом min/max лимитов"""
        p = chances[:]
        for _ in range(10): # Максимум 10 проходов для стабилизации
            current_sum = sum(p)
            if abs(current_sum - 1.0) < 1e-6:
                break
                
            diff = 1.0 - current_sum
            # Распределяем разницу между всеми элементами пропорционально их "свободному месту"
            if diff > 0:
                # Нужно увеличить
                total_room = sum(self.category_limits[categories[i]]["max"] - p[i] for i in range(len(p))) or 1.0
                for i in range(len(p)):
                    room = self.category_limits[categories[i]]["max"] - p[i]
                    p[i] += diff * (room / total_room)
            else:
                # Нужно уменьшить
                total_room = sum(p[i] - self.category_limits[categories[i]]["min"] for i in range(len(p))) or 1.0
                for i in range(len(p)):
                    room = p[i] - self.category_limits[categories[i]]["min"]
                    p[i] += diff * (room / total_room)
        
        return p

    def _greedy_adjust(
        self, 
        prices: List[float], 
        chances: List[float], 
        categories: List[str], 
        target_ev: float,
        max_iter: int = 100,
        eps: float = 1e-7
    ) -> Tuple[List[float], float]:
        """Жадная подстройка шансов для достижения целевого EV"""
        p = chances[:]
        n = len(p)
        
        for _ in range(max_iter):
            ev = sum(prices[i] * p[i] for i in range(n))
            if abs(ev - target_ev) <= eps:
                break
                
            # Если EV слишком большой, нужно переливать из дорогих в дешевые
            # Если EV слишком маленький, нужно переливать из дешевых в дорогие
            is_too_high = ev > target_ev
            
            # Сортируем для переливания
            # asc: дешевые -> дорогие, desc: дорогие -> дешевые
            asc = sorted(range(n), key=lambda i: prices[i])
            desc = asc[::-1]
            
            moved = False
            if is_too_high:
                # Нужно уменьшить EV: забираем у дорогих (j), отдаем дешевым (i)
                for j in desc:
                    avail_j = p[j] - self.category_limits[categories[j]]["min"]
                    if avail_j <= eps: continue
                    
                    for i in asc:
                        if i == j: continue
                        room_i = self.category_limits[categories[i]]["max"] - p[i]
                        if room_i <= eps: continue
                        
                        price_diff = prices[j] - prices[i]
                        if price_diff <= eps: continue
                        
                        need = (ev - target_ev) / price_diff
                        delta = min(avail_j, room_i, need, 0.02) # Ограничиваем шаг для плавности
                        
                        p[j] -= delta
                        p[i] += delta
                        ev -= delta * price_diff
                        moved = True
                        if ev <= target_ev: break
                    if ev <= target_ev: break
            else:
                # Нужно увеличить EV: забираем у дешевых (i), отдаем дорогим (j)
                for i in asc:
                    avail_i = p[i] - self.category_limits[categories[i]]["min"]
                    if avail_i <= eps: continue
                    
                    for j in desc:
                        if i == j: continue
                        room_j = self.category_limits[categories[j]]["max"] - p[j]
                        if room_j <= eps: continue
                        
                        price_diff = prices[j] - prices[i]
                        if price_diff <= eps: continue
                        
                        need = (target_ev - ev) / price_diff
                        delta = min(avail_i, room_j, need, 0.02)
                        
                        p[i] -= delta
                        p[j] += delta
                        ev += delta * price_diff
                        moved = True
                        if ev >= target_ev: break
                    if ev >= target_ev: break
            
            if not moved: break
            
        final_ev = sum(prices[i] * p[i] for i in range(n))
        return p, final_ev

    async def _update_case_price_only(self, db: AsyncSession, case_obj: Case):
        """
        Обновляет только цену кейса на основе фиксированных шансов и актуального флора.
        Используется для кейсов, где is_chance_distribution = False.
        """
        items_data = []
        for item in case_obj.items:
            # Даже если шансы фиксированные, мы берем актуальную цену
            price = item.sticker_catalog.floor_price_ton or 0.1
            items_data.append({"chance": item.chance, "price": price})

        if not items_data:
            return

        # Рассчитываем EV на основе фиксированных шансов из сида
        ev = sum(it["chance"] * it["price"] for it in items_data)
        
        # Целевая цена = EV / RTP
        target_price = ev / self.target_rtp
        final_price = math.ceil(target_price * 100) / 100
        
        if abs(case_obj.price_ton - final_price) > 0.001:
            logger.info(f"ChanceService: Updating fixed-chance case price {case_obj.slug}: {case_obj.price_ton} -> {final_price} TON")
            case_obj.price_ton = final_price
            case_obj.price_stars = round(final_price / settings.STARS_TO_TON_RATE)

        await db.commit()

    # async def _simple_pool_check(self, db: AsyncSession, case_obj: Case):
    #     """Упрощенная проверка наличия в пуле (предыдущая логика)"""
    #     items: list[CaseItem] = case_obj.items
    #     available_items = []
    #     unavailable_chance_sum = 0.0

    #     for item in items:
    #         count = await crud_sticker.count_available_in_pool(db, item.sticker_catalog_id)
    #         if count > 0:
    #             available_items.append(item)
    #         else:
    #             unavailable_chance_sum += item.chance
    #             item.chance = 0.0

    #     if unavailable_chance_sum > 0 and available_items:
    #         current_available_sum = sum(item.chance for item in available_items)
    #         if current_available_sum > 0:
    #             for item in available_items:
    #                 item.chance += (item.chance / current_available_sum) * unavailable_chance_sum
    #         else:
    #             equal_share = unavailable_chance_sum / len(available_items)
    #             for item in available_items:
    #                 item.chance = equal_share
        
    #     await db.commit()

chance_service = ChanceService()