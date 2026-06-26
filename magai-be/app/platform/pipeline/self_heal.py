import logging

logger = logging.getLogger(__name__)


SELF_HEAL_PROMPT = """The following React code failed to compile with this error:

{error}

Here is the original code:
```tsx
{source_code}
```

Fix the syntax error while preserving the logic, structure, and styling.
Return only the corrected, complete .tsx code."""


async def self_heal(agent, source_code: str, error: str, max_retries: int = 3) -> str:
    for attempt in range(1, max_retries + 1):
        logger.info("Self-heal attempt %d/%d", attempt, max_retries)
        prompt = SELF_HEAL_PROMPT.format(source_code=source_code, error=error)
        response = await agent.chat(prompt)
        corrected = await response.text()
        if corrected:
            return corrected
    raise RuntimeError(f"Self-heal failed after {max_retries} attempts")
