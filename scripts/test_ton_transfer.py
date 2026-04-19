import asyncio
import os
import sys
from loguru import logger

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from tonutils.clients import TonapiClient
from tonutils.clients.protocol import NetworkGlobalID
from tonutils.contracts.wallet import (
    WalletV4R2, WalletV3R2, WalletV4R1, WalletV3R1, 
    WalletV5R1, WalletV5Beta
)
from tonutils.utils import to_nano

async def test_ton_transfer():
    """
    Тестовый перевод 0.30 TON с серверного кошелька.
    """
    network_name = "TESTNET" if settings.IS_TESTNET else "MAINNET"
    logger.info(f"🧪 Starting TON Transfer Test (Multi-version Discovery) on {network_name}...")

    # Параметры из запроса
    DESTINATION_ADDRESS = "UQBiKevgEcPjgDo0JxTvodoutF8YVD9Lu8AcuJ0CnuWldL31"
    AMOUNT_TON = 0.30
    
    # Проверка конфигурации
    if not settings.TON_API_KEY:
        logger.error("❌ TON_API_KEY is not set in .env")
        return
    
    if not settings.NFT_SENDER_MNEMONIC:
        logger.error("❌ NFT_SENDER_MNEMONIC is not set in .env")
        return

    try:
        # 1. Инициализация клиента
        client = TonapiClient(
            api_key=settings.TON_API_KEY,
            network=NetworkGlobalID.TESTNET if settings.IS_TESTNET else NetworkGlobalID.MAINNET
        )
        await client.connect()
        
        # 2. Инициализация кошелька из мнемоники (24 слова)
        mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
        
        # Проверяем несколько версий кошелька, чтобы найти тот, где есть баланс
        wallet_versions = [
            ("V5R1", WalletV5R1),
            ("V5Beta", WalletV5Beta),
            ("V4R2", WalletV4R2),
            ("V4R1", WalletV4R1),
            ("V3R2", WalletV3R2),
            ("V3R1", WalletV3R1)
        ]
        
        active_wallet = None
        current_balance_ton = 0.0
        
        logger.info("🔍 Searching for active wallet version...")
        base_url = "https://testnet.tonapi.io" if settings.IS_TESTNET else "https://tonapi.io"
        for version_name, wallet_class in wallet_versions:
            temp_wallet, _, _, _ = wallet_class.from_mnemonic(client, mnemonic_list)
            temp_addr = temp_wallet.address.to_str()
            
            logger.debug(f"Checking {version_name}: {base_url}/v2/blockchain/accounts/{temp_addr}")
            try:
                account_info = await client.get_info(temp_addr)
                # В новой версии библиотеки это объект, а не словарь
                if hasattr(account_info, "balance"):
                    balance_nano = int(account_info.balance)
                elif isinstance(account_info, dict):
                    balance_nano = int(account_info.get("balance", 0))
                else:
                    logger.warning(f"   - {version_name}: Unknown response type {type(account_info)}")
                    balance_nano = 0
                
                balance_ton = balance_nano / 10**9
                logger.info(f"   - {version_name}: {temp_addr} | Balance: {balance_ton:.4f} TON")
                
                if balance_ton > 0 and active_wallet is None:
                    active_wallet = temp_wallet
                    current_balance_ton = balance_ton
                    logger.success(f"⭐ Found active wallet: {version_name}")
            except Exception as e:
                if "404" in str(e):
                    logger.warning(f"   - {version_name}: {temp_addr} | 404 (Not Found)")
                else:
                    logger.error(f"   - {version_name}: Error: {e}")

        if not active_wallet:
            # Если не нашли активный, используем V5R1 по умолчанию (но он будет с 0 балансом)
            active_wallet, _, _, _ = WalletV5R1.from_mnemonic(client, mnemonic_list)
            logger.warning("⚠️ No active wallet found with balance > 0. Using V5R1 as default.")

        logger.info(f"Final Sender Address: {active_wallet.address.to_str()}")
        logger.info(f"Target Address: {DESTINATION_ADDRESS}")
        logger.info(f"Amount to Send: {AMOUNT_TON} TON")
        logger.info(f"Current Balance: {current_balance_ton:.4f} TON")
        
        if current_balance_ton < (AMOUNT_TON + 0.05): # Запас на газ
            logger.error(f"❌ Insufficient balance for transfer + gas. Need at least {AMOUNT_TON + 0.05} TON")
            # Мы не выходим здесь, чтобы ты увидел адреса всех версий в логах
            return

        # 4. Выполнение перевода
        logger.info("Sending transaction...")
        ext_msg = await active_wallet.transfer(
            destination=DESTINATION_ADDRESS,
            amount=to_nano(AMOUNT_TON, 9),
            body="Stress Test: 0.30 TON Transfer"
        )
        tx_hash = ext_msg.hash if hasattr(ext_msg, "hash") else str(ext_msg)

        if tx_hash:
            logger.success(f"✅ TON Transfer successful! TX Hash: {tx_hash}")
            explorer_url = f"https://{'testnet.' if settings.IS_TESTNET else ''}tonviewer.com/transaction/{tx_hash}"
            logger.info(f"Check transaction here: {explorer_url}")
        else:
            logger.error("❌ Transfer failed (no hash returned)")

    except Exception as e:
        logger.error(f"❌ Test encountered an error: {e}")
    finally:
        if 'client' in locals() and client:
            await client.close()
            logger.info("Connection closed.")

if __name__ == "__main__":
    asyncio.run(test_ton_transfer())
