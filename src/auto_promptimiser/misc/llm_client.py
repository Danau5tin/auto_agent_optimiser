import asyncio
import copy
import os
import random
from typing import List, Dict, Any, Optional
from litellm import acompletion
from litellm.exceptions import InternalServerError


def _apply_anthropic_caching_if_possible(messages: List[Dict[str, Any]], model: str) -> List[Dict[str, Any]]:
    """Apply prompt caching for Anthropic models.
    
    Args:
        messages: List of message dictionaries
        model: Model name
        
    Returns:
        Messages with cache_control applied for Anthropic models
    """
    # Only apply caching for Anthropic models
    if not (model and "anthropic/" in model):
        return messages
    
    # Deep copy messages to avoid modifying the original
    cached_messages = copy.deepcopy(messages)
    
    # Find indices of system and user messages
    system_idx = None
    user_indices = []
    
    for i, msg in enumerate(cached_messages):
        if msg.get("role") == "system":
            system_idx = i
        elif msg.get("role") == "user":
            user_indices.append(i)
    
    # Apply cache control to system message
    if system_idx is not None:
        msg = cached_messages[system_idx]
        # Convert content to the format required for caching
        if isinstance(msg.get("content"), str):
            msg["content"] = [
                {
                    "type": "text",
                    "text": msg["content"],
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        elif isinstance(msg.get("content"), list):
            # Add cache_control to existing content items
            for item in msg["content"]:
                if isinstance(item, dict) and "text" in item:
                    item["cache_control"] = {"type": "ephemeral"}
    
    # Apply cache control to last 2 user messages
    if len(user_indices) >= 1:
        # Cache the last user message
        last_user_idx = user_indices[-1]
        msg = cached_messages[last_user_idx]
        if isinstance(msg.get("content"), str):
            msg["content"] = [
                {
                    "type": "text",
                    "text": msg["content"],
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        elif isinstance(msg.get("content"), list):
            for item in msg["content"]:
                if isinstance(item, dict) and "text" in item:
                    item["cache_control"] = {"type": "ephemeral"}
    
    if len(user_indices) >= 2:
        # Cache the second-to-last user message
        second_last_user_idx = user_indices[-2]
        msg = cached_messages[second_last_user_idx]
        if isinstance(msg.get("content"), str):
            msg["content"] = [
                {
                    "type": "text",
                    "text": msg["content"],
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        elif isinstance(msg.get("content"), list):
            for item in msg["content"]:
                if isinstance(item, dict) and "text" in item:
                    item["cache_control"] = {"type": "ephemeral"}
    
    return cached_messages


async def get_llm_response(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    max_retries: int = 10,
    **kwargs,
) -> str:
    
    kwargs = kwargs or {}
    # Use provided params or fall back to env vars
    model = model or os.getenv("LITELLM_MODEL", None)
    if not model:
        raise ValueError("Model must be specified either as argument or via LITELLM_MODEL env var.")
    temperature = temperature if temperature is not None else float(os.getenv("LITELLM_TEMPERATURE", "0.7"))
    
    # Apply Anthropic caching if applicable
    processed_messages = _apply_anthropic_caching_if_possible(messages, model)
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            # Call LiteLLM
            response = await acompletion(
                model=model,
                messages=processed_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                api_base=api_base,
            )
            return response.choices[0].message.content # type: ignore
        
        except InternalServerError as e:
            # Check if it's an Anthropic overloaded error
            if "overloaded_error" in str(e):
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    base_delay = 2 ** attempt  # 1, 2, 4, 8, 16, 32, 64
                    jitter = random.uniform(0, base_delay * 0.1)  # Add up to 10% jitter
                    delay = min(base_delay + jitter, 60)  # Cap at 60 seconds
                    
                    print(f"Anthropic overloaded, retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
        
        except Exception:
            raise
    
    # Should never reach here, but just in case
    raise RuntimeError("Failed to get LLM response after maximum retries.")