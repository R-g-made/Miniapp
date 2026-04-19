import asyncio
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.getgems_service import getgems_service

async def test_withdraw_specific_nft():
    """
    Тест вывода конкретного NFT (NFT 2.0) с серверного кошелька.
    """
    logger.info("🧪 Starting Specific NFT Withdrawal Test...")

    # Параметры из запроса пользователя
    NFT_ADDRESS = "EQBTAEVJC-3m8ehhUxGAQsIQ23BDU82kzDCwTVHSaC-1xFHY"
    
    # Адрес получателя (замени на свой, если нужно)
    # По умолчанию используем тестовый адрес из других скриптов
    DESTINATION_ADDRESS = "UQBiKevgEcPjgDo0JxTvodoutF8YVD9Lu8AcuJ0CnuWldL31"
    
    # Цена для расчета роялти (если требуется процентное роялти)
    PRICE_TON = 1.0

    # Проверка конфигурации
    if not settings.NFT_SENDER_MNEMONIC:
        logger.error("❌ NFT_SENDER_MNEMONIC is not set in .env")
        return

    try:
        logger.info(f"Initiating withdrawal of NFT: {NFT_ADDRESS}")
        logger.info(f"From (Server Wallet): V5R1")
        logger.info(f"To (Destination): {DESTINATION_ADDRESS}")

        # Выполняем трансфер
        tx_hash = await getgems_service.transfer_nft(
            nft_address=NFT_ADDRESS,
            destination_address=DESTINATION_ADDRESS,
            price_ton=PRICE_TON
        )

        if tx_hash:
            logger.success(f"✅ NFT Withdrawal successful! TX Hash: {tx_hash}")
            network_prefix = "testnet." if settings.IS_TESTNET else ""
            logger.info(f"Explorer: https://{network_prefix}tonviewer.com/transaction/{tx_hash}")
        else:
            logger.error("❌ NFT Withdrawal failed. Check logs for details (e.g., royalties or ownership).")

    except Exception as e:
        logger.error(f"❌ Test encountered an error: {e}")

if __name__ == "__main__":
    asyncio.run(test_withdraw_specific_nft())
