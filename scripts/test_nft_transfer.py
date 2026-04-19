import asyncio
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import settings
from backend.services.getgems_service import getgems_service

async def test_nft_transfer():
    """
    Реальный тест трансфера NFT с отправкой роялти на 2 адреса (Коллекция и Фонд).
    """
    logger.info("🧪 Starting NFT 2.0 Transfer Test...")

    # Параметры для теста (ЗАМЕНИ НА РЕАЛЬНЫЕ ДЛЯ ТЕСТНЕТА)
    # Используем аргументы командной строки или значения из настроек
    nft_addr = sys.argv[1] if len(sys.argv) > 1 else "EQB..." 
    dest_addr = sys.argv[2] if len(sys.argv) > 2 else "UQBiKevgEcPjgDo0JxTvodoutF8YVD9Lu8AcuJ0CnuWldL31"
    price = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    # Проверка настроек
    if not settings.NFT_SENDER_MNEMONIC:
        logger.error("❌ NFT_SENDER_MNEMONIC is not set in .env")
        return

    try:
        logger.info(f"Initiating transfer of {nft_addr} to {dest_addr}")
        
        # Обновляем TON API параметры для GetGemsService перед использованием
        network_id = -3 if settings.IS_TESTNET else -239
        base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
        
        logger.info(f"Connecting to {base_url} (Network ID: {network_id})")

        tx_hash = await getgems_service.transfer_nft(
            nft_address=nft_addr,
            destination_address=dest_addr,
            price_ton=price
        )

        if tx_hash:
            logger.success(f"✅ NFT Transfer successful! TX Hash: {tx_hash}")
            logger.info(f"Check transaction here: https://{'testnet.' if settings.IS_TESTNET else ''}tonviewer.com/transaction/{tx_hash}")
        else:
            logger.error("❌ NFT Transfer failed (see logs above)")

    except Exception as e:
        logger.error(f"❌ Test encountered an error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_nft_transfer())
