import asyncio
import json
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

# Создаем фейковый модуль config ДО ТОГО, как импортировать сервисы бэкенда
# Это предотвращает циклический импорт и ошибку БД
import types
dummy_config = types.ModuleType('backend.core.config')
dummy_config.settings = MagicMock()
dummy_config.settings.async_database_url = "sqlite+aiosqlite:///:memory:"
dummy_config.settings.REDIS_URL = "redis://localhost"
dummy_config.settings.STARS_TO_TON_RATE = 0.01
sys.modules['backend.core.config'] = dummy_config

from backend.services.tournament import tournament_service
from backend.models.user import User
from backend.models.sticker import UserSticker

async def run_mock_test():
    print("🚀 Starting Mocked Tournament Distribution Test (NO DATABASE)...")

    # 1. Готовим фейковый конфиг турнира
    config_path = os.path.join(os.getcwd(), "tournament_config.json")
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=1)
    end_time = now - timedelta(minutes=10) # Турнир закончился 10 мин назад
    
    fake_sticker_id = str(uuid4())
    
    config_data = {
        "Tournament": {
            "Setting": {
                "start_time": start_time.strftime("%d.%m.%Y %H:%M:%S"),
                "end_time": end_time.strftime("%d.%m.%Y %H:%M:%S"),
                "is_distributed": False,
                "max_place": 50
            },
            "PrizeByPlace": {
                "1": {
                    "catalog_id": str(uuid4()),
                    "sticker_pool_id": fake_sticker_id
                },
                "else": {
                    "ton_balance": "+0.77"
                }
            }
        }
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)
        
    # 2. Создаем фейковых пользователей прямо в памяти
    user1 = User(id=uuid4(), username="winner_1", balance_ton=0.0)
    user2 = User(id=uuid4(), username="loser_2", balance_ton=1.0) # У него уже есть 1 TON
    
    fake_top_users = [
        (user1, 1000.0), # 1 место
        (user2, 500.0)   # 2 место (получит 'else' награду)
    ]
    
    # 3. Создаем фейковый стикер
    fake_sticker = UserSticker(id=uuid4(), owner_id=None, is_available=True)
    
    # 4. Настраиваем перехватчики (mocks)
    mock_db_session = AsyncMock()
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = fake_sticker
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db_session
    
    with patch("backend.services.tournament.async_session_factory", mock_session_factory), \
         patch("backend.services.tournament.tournament_crud.get_top_users_by_volume", new_callable=AsyncMock) as mock_crud, \
         patch("backend.services.tournament.redis_service.connect", new_callable=AsyncMock), \
         patch.object(tournament_service, 'get_settings', return_value=config_data["Tournament"]["Setting"]), \
         patch.object(tournament_service, 'get_prizes', return_value=config_data["Tournament"]["PrizeByPlace"]):
         
        mock_crud.return_value = fake_top_users
        
        print("\n[+] Triggering prize distribution logic...")
        await tournament_service.update_leaderboard()
        
    print("\n[+] Checking Results...")
    
    # Проверяем 1 место (Стикер)
    if fake_sticker.owner_id == user1.id:
        print(f"✅ Place 1 ({user1.username}): SUCCESS - Received Sticker")
    else:
        print(f"❌ Place 1 ({user1.username}): FAILED - Did not receive sticker")
        
    # Проверяем 2 место (ТОНы)
    if user2.balance_ton == 1.77: # Было 1.0, добавили 0.77
        print(f"✅ Place 2 ({user2.username}): SUCCESS - Received 0.77 TON (New Balance: {user2.balance_ton})")
    else:
        print(f"❌ Place 2 ({user2.username}): FAILED - Expected 1.77 TON, got {user2.balance_ton}")
        
    # Проверяем обновился ли конфиг
    with open(config_path, "r", encoding="utf-8") as f:
        updated_config = json.load(f)
        if updated_config["Tournament"]["Setting"]["is_distributed"]:
            print("✅ Config: SUCCESS - 'is_distributed' is set to True")
        else:
            print("❌ Config: FAILED - 'is_distributed' is still False")

if __name__ == "__main__":
    asyncio.run(run_mock_test())