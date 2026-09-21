import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    endpoint: str
    deployment: str
    temperature: float = 0.0
    max_retries: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT", "").strip()
        deployment = os.getenv("AZURE_FOUNDRY_DEPLOYMENT", "").strip()
        if not endpoint or not deployment:
            raise ValueError("AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_DEPLOYMENT are required")
        return cls(endpoint, deployment, float(os.getenv("TRANSLATION_TEMPERATURE", "0")), int(os.getenv("TRANSLATION_MAX_RETRIES", "5")))