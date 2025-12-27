from dataclasses import dataclass
from typing import Dict


# Cijene su po 1M tokena (USD)
MODEL_PRICING = {
    "gpt-4.1-mini": {
        "input": 0.20,
        "output": 0.80,
    },
    "gpt-4.1": {
        "input": 1,
        "output": 4,
    },
}


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class PricingCalculator:
    def __init__(self, model: str):
        if model not in MODEL_PRICING:
            raise ValueError(f"Unknown pricing for model: {model}")
        self.model = model
        self.pricing = MODEL_PRICING[model]

    def calculate(self, usage: Usage) -> Dict:
        input_cost = (
            usage.prompt_tokens / 1_000_000
        ) * self.pricing["input"]

        output_cost = (
            usage.completion_tokens / 1_000_000
        ) * self.pricing["output"]

        total_cost = round(input_cost + output_cost, 6)

        return {
            "model": self.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": total_cost,
            "breakdown": {
                "input_cost_usd": round(input_cost, 6),
                "output_cost_usd": round(output_cost, 6),
            },
        }