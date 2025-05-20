import json
import os

from dotenv import load_dotenv

# 환경 변수 로드
dotenv_path = os.path.join(os.path.dirname(__file__), "../../.env")  # .env 파일 경로 지정
load_dotenv(dotenv_path, override=True)  # 🔄 기존 환경 변수 덮어쓰기

class Settings:
    API_KEY: str = os.getenv("API_KEY")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    FMP_BASE_URL: str = os.getenv("FMP_BASE_URL") 
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN") 
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID") 

settings = Settings()

print(f"🔑 Loaded API_KEY: {settings.API_KEY}")  # 디버깅용
print(f"🔑 Loaded OPENAI_API_KEY: {settings.OPENAI_API_KEY}")  # 디버깅용
print(f"🔑 Loaded FMP_BASE_URL: {settings.FMP_BASE_URL}")  # 디버깅용

def save_strategy(user_id: str, strategy: dict):
    """사용자의 전략을 파일로 저장합니다."""
    with open(f"strategies/{user_id}_strategy.json", "w") as file:
        json.dump(strategy, file)

def load_strategy(user_id: str) -> dict:
    """사용자의 전략을 파일에서 불러옵니다."""
    if os.path.exists(f"strategies/{user_id}_strategy.json"):
        with open(f"strategies/{user_id}_strategy.json", "r") as file:
            return json.load(file)
    else:
        return {}
