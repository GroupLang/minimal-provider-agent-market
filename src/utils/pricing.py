import json
from dataclasses import dataclass
from typing import Dict, Optional

import httpx
from loguru import logger


@dataclass
class ModelPricing:
    input_price_per_token: float
    output_price_per_token: float


DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"


class PricingStrategy:
    def __init__(self, openrouter_api_key: str):
        self.openrouter_api_key = openrouter_api_key
        self._model_prices: Dict[str, ModelPricing] = {}
        self._current_bid: float = 0.03
        self._backoff_factor: float = 0.8
        self._increase_factor: float = 1.2
        self._min_bid: float = 0.03
        self._max_bid: float = 0.03
        self._last_profitable: bool = False

    def update_model_prices(self, models_data: list) -> None:
        """Update model prices from provided OpenRouter API data."""
        self._model_prices.clear()
        for model in models_data:
            self._model_prices[model["id"]] = ModelPricing(
                input_price_per_token=model.get("pricing", {}).get("prompt", 0),
                output_price_per_token=model.get("pricing", {}).get("completion", 0),
            )
        logger.info("Successfully updated model prices")

    def estimate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost for a given model and token usage."""
        if model_id not in self._model_prices:
            logger.warning(f"No pricing information for model {model_id}")
            model_id = DEFAULT_MODEL

        pricing = self._model_prices[model_id]
        return input_tokens * float(pricing.input_price_per_token) + output_tokens * float(
            pricing.output_price_per_token
        )

    def calculate_next_bid(self, was_profitable: Optional[bool] = None) -> float:
        """Calculate the next bid using exponential backoff strategy."""
        if was_profitable is None:
            return self._current_bid

        if was_profitable:
            pass
        else:
            self._current_bid = max(self._current_bid * self._backoff_factor, self._min_bid)

        self._last_profitable = was_profitable
        return round(self._min_bid, 2)

    def reset_strategy(self) -> None:
        """Reset the bidding strategy to initial state."""
        self._current_bid = 1
        self._last_profitable = False
