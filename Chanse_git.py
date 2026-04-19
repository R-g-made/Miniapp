from typing import Any, Optional

import requests
from core.celery import celery_app

from django.db import transaction
from users.models import CustomUser
from packs.serializers import RequestLiquiditySerializer
from packs.models import UserInventory
from cases.models import Case, CaseStatus, CaseItem

from .models import Pack


@celery_app.task
def update_sticker_prices_task() -> None:
    response = requests.get("https://stickers.tools/api/stats-new")
    data = response.json()
    sticker_pack_collections = data.get("collections")
    update_packs_prices_sticker_pack(sticker_pack_collections)
    calculate_cases_price()

    # TODO: сюда добавлять функции для изменения цен на стикеры сторов


def update_packs_prices_sticker_pack(collections: dict) -> dict:
    packs = Pack.objects.filter(contributor="Sticker Pack").values(
        "collection_name", "pack_name"
    )

    valid_pack_names = {p["pack_name"] for p in packs}
    valid_collections = {p["collection_name"] for p in packs}

    sticker_pack_data = {}

    for col_data in collections.values():
        collection_name = col_data["name"]

        if collection_name not in valid_collections:
            continue

        for pack_data in col_data.get("stickers", {}).values():
            pack_name = pack_data["name"]
            if pack_name not in valid_pack_names:
                continue

            price = (
                pack_data.get("current", {})
                .get("price", {})
                .get("median", {})
                .get("ton")
            )

            if not price:
                continue

            sticker_pack_data.setdefault(collection_name, {})[pack_name] = price

            packs_to_update = []
            try:
                with transaction.atomic():
                    for collection, packs in sticker_pack_data.items():
                        for pack_name, price in packs.items():
                            try:
                                obj = Pack.objects.get(
                                    collection_name=collection,
                                    pack_name=pack_name
                                )
                                obj.price = price
                                packs_to_update.append(obj)
                            except Pack.DoesNotExist:
                                continue

                    if packs_to_update:
                        Pack.objects.bulk_update(packs_to_update, ["price"])
            except Exception as e:
                print(f"Ошибка обновления Sticker Pack: {e}")


"""
Формула фи:
Для айтема:
Цена айтема * шанс / 100к
Фи кейса:
Цена кейса - Сума айтемов/ цена кейса
"""


def adjust_case_price(items_dict: dict, base_fee: float, percent: int = 5) -> tuple[float, float]:
    EV = sum(v["price"] * v["chance"] for v in items_dict.values())
    min_fee = base_fee - base_fee * percent / 100
    max_fee = base_fee + base_fee * percent / 100

    case_price_min = EV / (1 - max_fee / 100)
    case_price_max = EV / (1 - min_fee / 100)

    case_price_new = (case_price_min + case_price_max) / 2
    case_price_new = round(case_price_new * 2) / 2  # округление до 0.5

    new_fee = (case_price_new - EV) / case_price_new * 100

    return case_price_new, new_fee


def _rebalance_probs_greedy(  # noqa: C901
        prices: list[float], probs: list[float], target_ev: float, min_p: float, max_p: float, eps: float = 1e-9
) -> tuple[list[float], float]:
    n = len(prices)
    p = probs[:]
    ev = sum(prices[i] * p[i] for i in range(n))
    if abs(ev - target_ev) <= eps:
        return p, ev

    asc = sorted(range(n), key=lambda i: prices[i])
    desc = asc[::-1]

    if ev > target_ev:
        i_ptr, j_ptr = 0, 0
        while ev - target_ev > eps and i_ptr < n and j_ptr < n:
            i = asc[i_ptr]
            j = desc[j_ptr]
            if prices[j] <= prices[i]:
                break

            room_i = max_p - p[i]
            avail_j = p[j] - min_p
            if room_i <= eps:
                i_ptr += 1
                continue
            if avail_j <= eps:
                j_ptr += 1
                continue

            need = (ev - target_ev) / (prices[j] - prices[i])
            delta = min(room_i, avail_j, need)
            if delta <= eps:
                break

            p[i] += delta
            p[j] -= delta
            ev -= delta * (prices[j] - prices[i])
    else:
        i_ptr, j_ptr = 0, 0
        while target_ev - ev > eps and i_ptr < n and j_ptr < n:
            i = asc[i_ptr]
            if prices[j] <= prices[i]:
                break

            avail_i = p[i] - min_p
            room_j = max_p - p[j]
            if avail_i <= eps:
                i_ptr += 1
                continue
            if room_j <= eps:
                j_ptr += 1
                continue

            need = (target_ev - ev) / (prices[j] - prices[i])
            delta = min(avail_i, room_j, need)
            if delta <= eps:
                break

            p[i] -= delta
            p[j] += delta
            ev += delta * (prices[j] - prices[i])

    return p, ev


def rebalance_chances(  # noqa: C901
        items: dict[str, dict[str, Any]],
        case_price: float,
        base_fee: float,
        case_name: str,
        percent: int = 5,
        max_iter: int = 100,
):
    """
    Распределение шансов с категориями и контролем EV/фи.
    Поддерживаются несколько cheap и expensive паков.
    При изменении базового fee шансы пересчитываются.
    Greedy-подстройка применяется только для medium/expensive, min/max соблюдаются.
    """
    names = list(items.keys())
    prices = [items[n]["price"] for n in names]
    n = len(prices)

    # --- Категории ---
    categories: list[Optional[str]] = [None] * n
    min_price, max_price = min(prices), max(prices)
    for i in range(n):
        if prices[i] == min_price:
            categories[i] = "cheap"
        elif prices[i] == max_price:
            categories[i] = "expensive"
        else:
            categories[i] = "medium"

    # --- Конфигурация категорий ---
    CATEGORY = {
        "cheap": {"min": 0.20, "max": 0.95, "weight": 2},
        "medium": {"min": 0.05, "max": 0.20, "weight": 0.5},
        "expensive": {"min": 0.0025, "max": 0.05, "weight": 0.05},
    }

    for i, cat in enumerate(categories):
        if cat == "cheap":
            items[names[i]]["chance"] = CATEGORY["cheap"]["max"]
        else:
            items[names[i]]["chance"] = CATEGORY[cat]["min"]  # type: ignore[index]

    def compute_chances(categories: list, CATEGORY: dict[str, dict[str, float]]) -> list[float]:
        names_local = list(items.keys())
        p = [items[n]["chance"] for n in names_local]
        main_cheap_indices = [i for i, c in enumerate(categories) if c == "cheap"]
        remaining_indices = [i for i in range(len(p)) if i not in main_cheap_indices]

        remaining_total = 1 - sum(p[i] for i in main_cheap_indices)
        weights = [CATEGORY[categories[i]]["weight"] for i in remaining_indices]
        weight_sum = sum(weights) or 1

        for i, w in zip(remaining_indices, weights):
            chance = w / weight_sum * remaining_total
            cat = categories[i]
            p[i] = max(CATEGORY[cat]["min"], min(chance, CATEGORY[cat]["max"]))

        total = sum(p)
        return [x / total for x in p]

    def greedy_adjust(
            prices: list[float],
            chances: list[float],
            categories: list[str | None],
            CATEGORY: dict[str, dict[str, float]],
            target_ev: float,
            eps: float = 1e-9,
            max_iter: int = 100,
            max_delta: float = 0.05,
    ) -> tuple[list[float], float]:
        p = chances[:]
        n = len(p)
        ev = sum(prices[i] * p[i] for i in range(n))
        asc = sorted(range(n), key=lambda i: prices[i])
        desc = asc[::-1]

        for _ in range(max_iter):
            if abs(ev - target_ev) <= eps:
                break
            for i in asc:
                if categories[i] == "cheap":
                    continue
                for j in desc:
                    if i == j or categories[j] == "cheap":
                        continue
                    if prices[j] <= prices[i]:
                        continue

                    room_i = CATEGORY[categories[i]]["max"] - p[i]  # type: ignore[index]
                    avail_j = p[j] - CATEGORY[categories[j]]["min"]  # type: ignore[index]
                    if room_i <= eps or avail_j <= eps:
                        continue

                    need = (ev - target_ev) / (prices[j] - prices[i])
                    delta = min(room_i, avail_j, abs(need), max_delta)

                    if ev > target_ev:
                        p[i] += delta
                        p[j] -= delta
                        ev -= delta * (prices[j] - prices[i])
                    else:
                        p[i] -= delta
                        p[j] += delta
                        ev += delta * (prices[j] - prices[i])

            # Clamp после каждой итерации
            for k in range(n):
                cat = categories[k]
                p[k] = max(CATEGORY[cat]["min"], min(p[k], CATEGORY[cat]["max"]))  # type: ignore[index]

        total = sum(p)
        return [x / total for x in p], ev

    # --- Основной цикл до попадания fee в диапазон ---
    for _ in range(30):  # кол-во попыток для попадания в диапазон
        chances_list = compute_chances(categories, CATEGORY)
        target_ev = case_price * (1 - base_fee / 100)
        chances_list, EV = greedy_adjust(prices, chances_list, categories, CATEGORY, target_ev, max_iter=max_iter)

        new_fee = (case_price - EV) / case_price * 100
        tol = base_fee * percent / 100
        if base_fee - tol <= new_fee <= base_fee + tol:
            break

        case_price_min = EV / (1 - (base_fee + percent) / 100)
        case_price_max = EV / (1 - (base_fee - percent) / 100)
        case_price = round((case_price_min + case_price_max) / 2 * 2) / 2

    # --- Обновление шансов и цены в БД ---
    updated_items: list[CaseItem] = []

    for i, n in enumerate(names):
        chance_value = chances_list[i]
        collection_name = items[n]["collection_name"]  # берем из словаря
        try:
            case_item = CaseItem.objects.get(
                case__name=case_name,
                pack__pack_name=n,
                pack__collection_name=collection_name,
            )
            case_item.chance = chance_value
            updated_items.append(case_item)
        except CaseItem.DoesNotExist:
            continue
        except CaseItem.MultipleObjectsReturned:
            case_item = (
                CaseItem.objects.filter(
                    case__name=case_name,
                    pack__pack_name=n,
                    pack__collection_name=collection_name,
                ).first()
            )
            if case_item:
                case_item.chance = chance_value
                updated_items.append(case_item)

    case = Case.objects.get(name=case_name)
    case.price = case_price
    case.current_fee = new_fee

    print(
        f"[rebalance] Кейc {case_name}: финальные шансы = "
        f"{[(n, round(items[n]['chance'], 4)) for n in names]}, "
        f"fee = {new_fee:.2f}%, цена = {case_price:.2f}"
    )

    return updated_items, [case]


def check_new_fee(new_fee: float, base_fee: float = 20, percent: int = 5) -> bool:
    tolerance = base_fee * percent / 100
    low = base_fee - tolerance
    high = base_fee + tolerance
    return low <= new_fee <= high


def calculate_cases_price() -> None:
    cases = Case.objects.filter(status=CaseStatus.ACTIVE)

    chances_to_update: list[CaseItem] = []
    cases_to_update: list[Case] = []

    for case in cases:
        case_price = float(case.price)
        case_base_fee = float(case.base_fee)

        items = CaseItem.objects.filter(case=case)

        items_dict = {
            item.pack.pack_name: {
                "price": float(item.pack.price),
                "chance": float(item.chance),
                "collection_name": item.pack.collection_name,
            }
            for item in items
        }

        EV = sum(v["price"] * v["chance"] for v in items_dict.values())
        current_fee = (case_price - EV) / case_price * 100

        valid = check_new_fee(current_fee, base_fee=case_base_fee)
        if valid:
            case.current_fee = current_fee
            cases_to_update.append(case)
        else:
            updated_items, updated_cases = rebalance_chances(
                items_dict, case_price, case_base_fee, case.name
            )

            chances_to_update.extend(updated_items)
            cases_to_update.extend(updated_cases)

            print(f"{case.name}: фи был невалиден, новые шансы будут подобраны")

        try:
            with transaction.atomic():
                if cases_to_update:
                    Case.objects.bulk_update(cases_to_update, ["current_fee", "price"])
                if chances_to_update:
                    CaseItem.objects.bulk_update(chances_to_update, ["chance"])
        except Exception as e:
            print(f"Ошибка при обновлении: {e}")