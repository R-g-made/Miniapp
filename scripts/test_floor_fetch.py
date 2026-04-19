import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, AsyncMock, patch
from loguru import logger
from uuid import uuid4

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock external_api_service before importing floor_price_service
mock_external_api_module = MagicMock()
mock_external_api_instance = MagicMock()
mock_external_api_instance.update_floor_price = AsyncMock(return_value=[])
mock_external_api_module.external_api_service = mock_external_api_instance
sys.modules['backend.services.external_api_service'] = mock_external_api_module

from backend.services.floor_price_service import floor_price_service

async def test_floor_fetch():
    """
    Test script to check what FloorPriceService returns and how it matches.
    """
    logger.info("Testing FloorPriceService._fetch_all_floors_from_tools()...")
    
    # 1. Test fetching from stickers.tools
    all_floors = await floor_price_service._fetch_all_floors_from_tools()
    
    if not all_floors:
        logger.error("Failed to fetch floors or received empty dictionary.")
        return

    logger.success(f"Successfully fetched floors for {len(all_floors)} collections.")
    
    # 2. Test matching logic with a mock catalog
    logger.info("\nTesting matching logic with mock catalogs...")
    
    class MockCatalog:
        def __init__(self, id, name, collection_name, floor_price_ton, is_onchain, collection_address):
            self.id = id
            self.name = name
            self.collection_name = collection_name
            self.floor_price_ton = floor_price_ton
            self.is_onchain = is_onchain
            self.collection_address = collection_address

    mock_catalogs = [
        MockCatalog(uuid4(), "Cook", "DOGS OG", 0.0, True, "EQ..."),
        MockCatalog(uuid4(), "Blue Wings", "Flappy Bird", 10.0, True, "EQ..."),
        MockCatalog(uuid4(), "Non Existent Pack", "Non Existent Collection", 1.0, True, "EQ...")
    ]
    
    # Mock DB session
    mock_db = AsyncMock()
    
    # We need to patch crud_sticker inside floor_price_service.update_all_prices
    with patch('app.services.floor_price_service.crud_sticker') as mock_crud:
        # Use side_effect for async functions in some cases, or just ensure it's an AsyncMock
        mock_crud.get_all_catalogs = AsyncMock(return_value=mock_catalogs)
        mock_crud.update_catalog_floor_price = AsyncMock()
        
        logger.info("Running floor_price_service.update_all_prices(mock_db)...")
        await floor_price_service.update_all_prices(mock_db)
    
    logger.success("Test completed. Check logs above to see matching and updates.")

if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    try:
        asyncio.run(test_floor_fetch())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
