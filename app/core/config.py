# app/core/config.py
import json
import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    API_KEY: str = os.getenv("API_KEY", "your_default_api_key")

settings = Settings()

def save_strategy(user_id: str, strategy: dict):
    with open(f"strategies/{user_id}_strategy.json", "w") as file:
        json.dump(strategy, file)

def load_strategy(user_id: str) -> dict:
    if os.path.exists(f"strategies/{user_id}_strategy.json"):
        with open(f"strategies/{user_id}_strategy.json", "r") as file:
            return json.load(file)
    else:
        return {}