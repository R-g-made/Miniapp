import asyncio
from backend.core.config import settings
from tonutils.clients import TonapiClient
from tonutils.contracts.wallet import WalletV5R1

async def test():
    # Используем -239 для mainnet и -3 для testnet
    network_id = -3 if settings.IS_TESTNET else -239
    base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
    
    print(f"Connecting to {base_url} with network_id {network_id}")
    
    client = TonapiClient(api_key=settings.TON_API_KEY, network=network_id, base_url=base_url)
    await client.connect()
    try:
        mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
        wallet, _, _, _ = WalletV5R1.from_mnemonic(client, mnemonic_list)
        print(f"Wallet address: {wallet.address.to_str()}")
        
        info = await client.get_info(wallet.address.to_str())
        print(f"Balance: {info.balance}")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test())
