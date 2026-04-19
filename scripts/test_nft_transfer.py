import asyncio
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.getgems_service import getgems_service

async def test_nft_transfer():
    """
    Реальный тест трансфера NFT с отправкой роялти на 2 адреса (Коллекция и Фонд).
    """
    logger.info("🧪 Starting NFT 2.0 Transfer Test...")

    # Параметры для теста (ЗАМЕНИ НА РЕАЛЬНЫЕ ДЛЯ ТЕСТНЕТА)
    TEST_NFT_ADDRESS = "EQB..." # Адрес NFT, которым владеет ваш серверный кошелек
    TEST_DESTINATION = "EQC..." # Адрес получателя
    TEST_PRICE = 10.0 # Цена для расчета роялти (5% = 0.5 TON)

    # Проверка настроек
    if not settings.NFT_SENDER_MNEMONIC:
        logger.error("❌ NFT_SENDER_MNEMONIC is not set in .env")
        return

    if settings.NFT_COLLECTION_ADDRESS == "EQ..." or settings.NFT_FUND_ADDRESS == "EQ...":
        logger.warning("⚠️ NFT_COLLECTION_ADDRESS or NFT_FUND_ADDRESS are still default. Set them in .env!")

    try:
        logger.info(f"Initiating transfer of {TEST_NFT_ADDRESS} to {TEST_DESTINATION}")
        logger.info(f"Fixed Royalties: 0.01 TON to Author, 0.01 TON to Fund ({settings.NFT_FUND_ADDRESS}), 0.01 TON to TG ({settings.NFT_TG_ADDRESS})")
        logger.info(f"Total Fixed Royalties: 0.03 TON")

        tx_hash = await getgems_service.transfer_nft(
            nft_address=TEST_NFT_ADDRESS,
            destination_address=TEST_DESTINATION,
            price_ton=TEST_PRICE
        )

        if tx_hash:
            logger.success(f"✅ NFT Transfer successful! TX Hash: {tx_hash}")
            logger.info(f"Check transaction here: https://{'testnet.' if settings.IS_TESTNET else ''}tonviewer.com/transaction/{tx_hash}")
        else:
            logger.error("❌ NFT Transfer failed (see logs above)")

    except Exception as e:
        logger.error(f"❌ Test encountered an error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        logger.info("Usage: python scripts/test_nft_transfer.py <nft_address> <destination_address> [price_ton]")
        logger.info("Example: python scripts/test_nft_transfer.py EQB... EQC... 10.0")
        
        # Если аргументы не переданы, используем значения по умолчанию для демонстрации
        # Но в реальности они должны быть переданы
        asyncio.run(test_nft_transfer())
    else:
        nft_addr = sys.argv[1]
        dest_addr = sys.argv[2]
        price = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
        
        # Переопределяем параметры внутри теста
        async def run_custom_test():
            tx_hash = await getgems_service.transfer_nft(
                nft_address=nft_addr,
                destination_address=dest_addr,
                price_ton=price
            )
            if tx_hash:
                logger.success(f"✅ Success! Hash: {tx_hash}")
            else:
                logger.error("❌ Failed")

        asyncio.run(run_custom_test())
