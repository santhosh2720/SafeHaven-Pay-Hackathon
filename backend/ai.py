import json
import os
from typing import Any

import httpx


class RiskAI:
    """Optional OpenAI-compatible explanation layer with a deterministic safe fallback."""

    def __init__(self) -> None:
        self.api_key = os.getenv('LLM_API_KEY', '').strip()
        self.base_url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
        self.model = os.getenv('LLM_MODEL', 'gpt-4o-mini').strip()

    @property
    def live(self) -> bool:
        return bool(self.api_key and self.model)

    async def explain(self, features: dict[str, Any], score: float, fallback: str) -> dict[str, str]:
        if not self.live:
            return {'reason': fallback, 'provider': 'deterministic-risk-engine', 'model': 'rules-fallback'}

        prompt = {
            'task': 'Explain a payment risk decision for a merchant in one concise sentence.',
            'risk_score': score,
            'features': features,
            'format': {'reason': 'string, 25 words maximum'},
        }
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.post(
                    f'{self.base_url}/chat/completions',
                    headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
                    json={
                        'model': self.model,
                        'temperature': 0.1,
                        'response_format': {'type': 'json_object'},
                        'messages': [
                            {'role': 'system', 'content': 'Return valid JSON only with a reason field. Never invent facts.'},
                            {'role': 'user', 'content': json.dumps(prompt)},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()['choices'][0]['message']['content']
                reason = json.loads(content).get('reason', '').strip()
                if reason:
                    return {'reason': reason, 'provider': 'openai-compatible', 'model': self.model}
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        return {'reason': fallback, 'provider': 'deterministic-risk-engine', 'model': 'rules-fallback'}
