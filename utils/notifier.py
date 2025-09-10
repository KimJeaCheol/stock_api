# utils/notifier.py
import logging
import os

from telegram import Bot
from telegram.error import TelegramError

from app.core.config import settings

logger = logging.getLogger(__name__)

async def notify_telegram(message: str, save_path: str = None, file_path: str = None):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram 설정 누락: 알림 전송 생략")
        return

    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

        # 📩 텍스트 메시지 전송
        await bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info("✅ Telegram 텍스트 전송 완료")

        # 🖼️ 이미지 전송
        if save_path and os.path.exists(save_path):
            with open(save_path, "rb") as img:
                await bot.send_photo(chat_id=settings.TELEGRAM_CHAT_ID, photo=img)
                logger.info(f"✅ Telegram 이미지 전송 완료: {save_path}")
        elif save_path:
            logger.warning(f"⚠️ 이미지 파일 존재 안 함: {save_path}")

        # 📄 파일(PDF) 전송
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as doc:
                await bot.send_document(chat_id=settings.TELEGRAM_CHAT_ID, document=doc)
                logger.info(f"✅ Telegram PDF 전송 완료: {file_path}")
        elif file_path:
            logger.warning(f"⚠️ 문서 파일 존재 안 함: {file_path}")

    except TelegramError as te:
        logger.error(f"Telegram 전송 실패 (TelegramError): {te}")
    except Exception as e:
        logger.error(f"Telegram 전송 실패 (Exception): {e}")
