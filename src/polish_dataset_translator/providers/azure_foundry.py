import json
import os
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI, OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from polish_dataset_translator.config import Settings


class AzureFoundryTranslator:
    def __init__(self, settings: Settings) -> None:
        credential = DefaultAzureCredential()
        endpoint = settings.endpoint.rstrip("/")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if "/openai/v1" in endpoint:
            base_url = endpoint.split("/responses", 1)[0].rstrip("/") + "/"
            token = api_key or credential.get_token("https://cognitiveservices.azure.com/.default").token
            self.client = OpenAI(base_url=base_url, api_key=token, timeout=60.0, max_retries=0)
        else:
            self.client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_version="2024-10-21",
                api_key=api_key,
                azure_ad_token_provider=None if api_key else get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default"),
                timeout=60.0,
                max_retries=0,
            )
        self.deployment = settings.deployment
        self.temperature = settings.temperature
        self.max_retries = settings.max_retries
        self.request_count = 0

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=30), reraise=True)
    def translate(self, text: str) -> str:
        return self.translate_many([text])[0]

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=30), reraise=True)
    def translate_many(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        request: dict[str, Any] = {
            "model": self.deployment,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Translate each English natural-language text to Polish. Preserve order, placeholders, URLs, format tokens, code fragments and literal identifiers. Return only JSON: {\"translations\":[\"...\"]}. The output array must have exactly the same length as the input array."},
                {"role": "user", "content": json.dumps({"texts": texts}, ensure_ascii=False)},
            ],
        }
        self.request_count += 1
        request_number = self.request_count
        print(f"[batch {request_number}] sending {len(texts)} texts ({sum(len(text) for text in texts)} chars) to {self.deployment}", flush=True)
        if not self.deployment.lower().startswith(("gpt-5", "o1", "o3", "o4")):
            request["temperature"] = self.temperature
        try:
            response = self.client.chat.completions.create(**request)
        except Exception as error:
            print(f"[batch {request_number}] failed: {error}", flush=True)
            raise
        content = response.choices[0].message.content or ""
        parsed: Any = json.loads(content)
        translations = parsed.get("translations") if isinstance(parsed, dict) else None
        if not isinstance(translations, list) or len(translations) != len(texts) or not all(isinstance(item, str) for item in translations):
            raise ValueError(f"Azure Foundry returned {len(translations) if isinstance(translations, list) else 'invalid'} translations for {len(texts)} inputs")
        print(f"[batch {request_number}] response received: {sum(len(item) for item in translations)} chars", flush=True)
        return translations