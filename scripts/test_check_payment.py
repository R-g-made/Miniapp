import asyncio
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import settings
from tonutils.clients import TonapiClient

async def test_check_payment():
    """
    Тест проверки транзакции в блокчейне по хешу.
    """
    if len(sys.argv) < 2:
        logger.error("Usage: python scripts/test_check_payment.py <tx_hash>")
        return

    tx_hash = sys.argv[1]
    logger.info(f"🧪 Checking transaction: {tx_hash}")

    # Используем -239 для mainnet и -3 для testnet
    network_id = -3 if settings.IS_TESTNET else -239
    base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
    
    client = TonapiClient(api_key=settings.TON_API_KEY, network=network_id, base_url=base_url)
    await client.connect()
    
    try:
        # Получаем данные о транзакции/сообщении
        # В tonutils поиск обычно идет через get_message или get_transaction
        logger.info(f"Fetching data from {base_url}...")
        
        # Попытка найти как сообщение (External Message)
        try:
            msg_data = await client.get_message(tx_hash)
            logger.success(f"✅ Found as Message!")
            logger.info(f"Destination: {msg_data.destination}")
            logger.info(f"Value: {msg_data.value} nanotons")
        except:
            logger.warning("Not found as message, checking as transaction...")
            
            # Попытка найти как транзакцию
            tx_data = await client.get_transaction(tx_hash)
            logger.success(f"✅ Found as Transaction!")
            if hasattr(tx_data, "in_msg"):
                logger.info(f"In Message Value: {tx_data.in_msg.value}")
                logger.info(f"Source: {tx_data.in_msg.source}")

    except Exception as e:
        logger.error(f"❌ Error checking payment: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_check_payment())
