from aiogram import Bot
from backend.core.config import settings
from loguru import logger
from typing import List, Optional

class NotificationService:
    """Сервис для отправки уведомлений админам и пользователям"""
    
    def __init__(self):
        self._bot: Optional[Bot] = None

    def set_bot(self, bot: Bot):
        self._bot = bot

    async def notify_admins(self, message: str):
        """Отправить сообщение всем админам из конфига"""
        if not self._bot:
            logger.warning("NotificationService: Bot not initialized")
            return

        if not settings.ADMIN_IDS:
            logger.warning("NotificationService: No admin IDs configured")
            return

        for admin_id in settings.ADMIN_IDS:
            try:
                await self._bot.send_message(admin_id, message, parse_mode="HTML")
            except Exception as e:
                logger.error(f"NotificationService: Failed to send message to {admin_id}: {e}")

notification_service = NotificationService()
