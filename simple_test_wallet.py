import asyncio
from backend.core.config import settings
from tonutils.clients import TonapiClient
from tonutils.contracts.wallet import WalletV5R1

async def test():
    client = TonapiClient(api_key=settings.TON_API_KEY, network='mainnet', base_url='https://tonapi.io/v2')
    await client.connect()
    try:
        mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
        if not mnemonic_list:
            print("Mnemonic is empty!")
            return
            
        wallet, _, _, _ = WalletV5R1.from_mnemonic(client, mnemonic_list)
        print(f"Wallet address: {wallet.address.to_str()}")
        
        info = await client.get_info(wallet.address.to_str())
        print(f"Balance: {info.balance}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test())
