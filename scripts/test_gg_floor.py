import asyncio
import json
from typing import Dict, Any, Optional

class MockGetGemsService:
    async def get_floor_price_from_mock_response(self, mock_response: Dict[str, Any], name_filter: str) -> Optional[float]:
        """
        Тестовая логика для парсинга ответа Getgems и поиска самого дешевого предмета
        """
        try:
            if not mock_response.get("success"):
                return None
                
            items = mock_response.get("response", {}).get("items", [])
            
            # Фильтруем по имени и наличию цены
            prices = []
            for item in items:
                name = item.get("name", "")
                sale = item.get("sale", {})
                
                # Ищем сходство по имени (регистронезависимо)
                if name_filter.lower() in name.lower():
                    # Проверяем оба поля цены: fullPrice и price
                    p1 = sale.get("fullPrice")
                    p2 = sale.get("price")
                    
                    val = None
                    if p1 and p2: val = min(int(p1), int(p2))
                    elif p1: val = int(p1)
                    elif p2: val = int(p2)
                    
                    if val:
                        prices.append({
                            "name": name,
                            "price": val
                        })
            
            if not prices:
                print(f"No items found matching '{name_filter}'")
                return None
            
            # Сортируем по цене (по возрастанию)
            prices.sort(key=lambda x: x["price"])
            
            cheapest = prices[0]
            price_ton = cheapest["price"] / 10**9
            
            print(f"Success! Absolute cheapest '{cheapest['name']}': {price_ton} TON")
            return price_ton
            
        except Exception as e:
            print(f"Error parsing mock response: {e}")
            return None

async def test_greatness_floor():
    # Данные для теста с разными полями цен
    mock_data = {
      "success": True,
      "response": {
        "items": [
          {
            "name": "Greatness #1",
            "sale": {
              "fullPrice": "1500000000", 
              "price": "1400000000" # Здесь price дешевле
            }
          },
          {
            "name": "Greatness #2",
            "sale": {
              "fullPrice": "1200000000", # Раньше это было самым дешевым
              "price": "1300000000"
            }
          },
          {
            "name": "Greatness Super Cheap",
            "sale": {
              "price": "900000000" # Самое дешевое только в поле price
            }
          }
        ]
      }
    }
    
    service = MockGetGemsService()
    
    print("\n--- Testing Absolute Cheapest Floor for 'Greatness' ---")
    price = await service.get_floor_price_from_mock_response(mock_data, "Greatness")
    
    if price == 0.9:
        print("Test PASSED: Found the absolute cheapest Greatness (0.9 TON)")
    else:
        print(f"Test FAILED: Expected 0.9, got {price}")

if __name__ == "__main__":
    asyncio.run(test_greatness_floor())
