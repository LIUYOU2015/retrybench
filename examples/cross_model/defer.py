"""Offline adapter fixture. This is not an evaluated language model."""


def predict(case):
    return {"action": "unresolved", "arguments": {"idempotency_key": None},
            "raw_response": {"fixture": "always-defer; synthetic"},
            "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0}}
