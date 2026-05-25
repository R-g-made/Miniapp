def calculate_case_economy(prices, X, RTP):
    """
    Автономный расчет цены кейса и шансов выпадения предметов.
    
    :param prices: list[float] - Список цен всех предметов в кейсе
    :param X: float - Множитель стоимости кейса от минимальной цены (например, 5)
    :param RTP: float - Желаемый возврат игроку (например, 0.9 для 90%)
    :return: dict - Словать с ценой кейса, коэффициентом k и списком предметов с их долями от 1
    """
    p_min = min(prices)
    case_price = p_min * X          # Автоматическая цена кейса (например, 0.15 * 5 = 0.75)
    target_ev = case_price * RTP    # Целевое математическое ожидание (0.75 * 0.9 = 0.675)

    # Внутренняя функция для расчета текущего EV при конкретном значении k
    def get_ev(k_val):
        total_weight = 0.0
        weighted_sum = 0.0
        for p in prices:
            w = 1.0 / (p ** k_val)
            total_weight += w
            weighted_sum += p * w
        return weighted_sum / total_weight

    # Численный поиск коэффициента k (Метод бисекции)
    low_k = 0.0
    high_k = 15.0  # Верхняя граница поиска для экстремальных разбросов цен
    k = 0.0

    # 100 итераций гарантируют точность до 15 знаков после запятой
    for _ in range(100):
        k = (low_k + high_k) / 2.0
        current_ev = get_ev(k)

        if current_ev > target_ev:
            low_k = k  # Если средняя цена слишком высокая, увеличиваем штраф (k)
        else:
            high_k = k  # Если слишком низкая — уменьшаем штраф

    # Считаем финальные веса на основе найденного k
    weights = [1.0 / (p ** k) for p in prices]
    total_weight = sum(weights)

    # Нормализуем веса в честные доли от 1 (чтобы сумма была строго равна 1)
    items_distribution = []
    for index, p in enumerate(prices):
        chance_in_fraction = weights[index] / total_weight  # Доля от 1
        items_distribution.append({
            "price": p,
            "chance": chance_in_fraction,                              # Точная математическая доля для сервера
            "chance_percent": f"{chance_in_fraction * 100:.2f}%"       # Строка для вывода на клиент
        })

    return {
        "case_price": case_price,
        "target_rtp": f"{RTP * 100:.1f}%",
        "solved_k": round(k, 4),
        "items": items_distribution
    }


# === ПРОВЕРКА ДЛЯ ВАШЕГО КЕЙСА СО СКРИНШОТА ===
case_prices = [70.00, 7.90, 3.90, 3.80, 2.50, 0.80, 0.60, 0.40, 0.15,70.00, 7.90, 3.90, 3.80, 2.50, 0.80, 0.60, 0.40, 0.15]
X_multiplier = 9.33
desired_rtp = 0.9

result = calculate_case_economy(case_prices, X_multiplier, desired_rtp)

# Красивый вывод результатов в консоль
print(f"Рекомендованная цена кейса: {result['case_price']} ∇")
print(f"Найденный коэффициент k: {result['solved_k']}")
print("\nРаспределение предметов:")
print(f"{'Цена':<10} | {'Доля от 1 (Для сервера)':<25} | {'Шанс в % (Для игрока)':<20}")
print("-" * 65)

for item in result["items"]:
    print(f"{item['price']:<10.2f} | {item['chance']:<25.8f} | {item['chance_percent']:<20}")

# Проверка суммы долей
sum_of_chances = sum(item["chance"] for item in result["items"])
print("-" * 65)
print(f"Проверка суммы всех долей (должна быть строго 1.0): {sum_of_chances}")