"""OpenAI LLM provider with structured outputs support"""

import json
import logging
from typing import Any, ClassVar

from openai import AsyncOpenAI
from pydantic import BaseModel, create_model

from seriesoftubes.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider"""

    SUPPORTED_MODELS: ClassVar[list[str]] = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4o-2024-08-06",
        "gpt-4-turbo",  # For testing JSON mode fallback
    ]

    # Models that support structured outputs
    STRUCTURED_OUTPUT_MODELS: ClassVar[list[str]] = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4o-2024-08-06",
    ]

    def __init__(self, api_key: str | None = None):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None

    def _create_nested_model(
        self, schema: dict[str, Any], model_name: str
    ) -> type[BaseModel]:
        """Create nested Pydantic model from schema"""
        properties = schema.get("properties", {})
        field_definitions = {}

        for field_name, field_schema in properties.items():
            field_type, default = self._convert_property(field_schema, field_name)
            field_definitions[field_name] = (field_type, default)

        return create_model(model_name, **field_definitions)

    def _convert_property(
        self, prop_schema: dict[str, Any], field_name: str
    ) -> tuple[type, Any]:
        """Convert a single property schema to Pydantic field"""
        prop_type = prop_schema.get("type")

        if prop_type == "string":
            return (str, ...)
        elif prop_type == "integer":
            return (int, ...)
        elif prop_type == "number":
            return (float, ...)
        elif prop_type == "boolean":
            return (bool, ...)
        elif prop_type == "array":
            items_schema = prop_schema.get("items", {})
            if items_schema.get("type") == "string":
                return (list[str], ...)
            elif items_schema.get("type") == "integer":
                return (list[int], ...)
            elif items_schema.get("type") == "number":
                return (list[float], ...)
            elif items_schema.get("type") == "object":
                # Recursive object in array
                item_model = self._create_nested_model(
                    items_schema, f"{field_name}_item"
                )
                return (list[item_model], ...)
            else:
                return (list[Any], ...)
        elif prop_type == "object":
            # Nested object
            nested_model = self._create_nested_model(prop_schema, field_name)
            return (nested_model, ...)
        else:
            # Fallback to Any
            return (Any, ...)

    def _json_schema_to_pydantic(self, schema: dict[str, Any]) -> type[BaseModel]:
        """Convert JSON schema to Pydantic model for structured outputs"""
        # Convert main schema
        properties = schema.get("properties", {})
        field_definitions = {}

        for field_name, field_schema in properties.items():
            field_type, default = self._convert_property(field_schema, field_name)
            field_definitions[field_name] = (field_type, default)

        return create_model("ResponseModel", **field_definitions)

    async def call(
        self,
        prompt: str,
        model: str,
        temperature: float,
        schema: dict[str, Any] | None = None,
    ) -> Any:
        """Call OpenAI API with optional structured outputs"""
        if not self.client:
            msg = "OpenAI API key not configured"
            raise ValueError(msg)

        # Validate model is supported
        if not self.validate_model(model):
            supported_models = ", ".join(self.SUPPORTED_MODELS)
            msg = f"Model '{model}' not supported. Supported models: {supported_models}"
            raise ValueError(msg)

        messages = [{"role": "user", "content": prompt}]

        try:
            # Use structured outputs for supported models
            if schema and model in self.STRUCTURED_OUTPUT_MODELS:
                # Convert JSON schema to Pydantic model
                response_model = self._json_schema_to_pydantic(schema)

                # Use the new structured outputs API
                completion = await self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_model,
                )

                message = completion.choices[0].message

                # Handle refusals in structured outputs
                if hasattr(message, "refusal") and message.refusal:
                    logger.warning(f"OpenAI structured output refusal: {message.refusal}")
                    # Include finish reason if available
                    finish_reason = completion.choices[0].finish_reason if hasattr(completion.choices[0], 'finish_reason') else None
                    if finish_reason:
                        logger.warning(f"Finish reason: {finish_reason}")
                    msg = f"OpenAI refused to respond: {message.refusal}"
                    raise ValueError(msg)

                # Return parsed structured output
                if hasattr(message, "parsed") and message.parsed:
                    return message.parsed.model_dump()
                else:
                    # Fallback to content parsing
                    return json.loads(message.content or "{}")

            else:
                # Fall back to regular completions API
                request_kwargs = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }

                # Add JSON mode for older models if schema is specified
                if schema:
                    request_kwargs["response_format"] = {"type": "json_object"}
                    messages[0]["content"] += "\n\nRespond with valid JSON."

                completion = await self.client.chat.completions.create(**request_kwargs)
                message = completion.choices[0].message
                content = message.content
                
                # Check if the response indicates a refusal
                if content and any(phrase in content.lower() for phrase in ["i'm sorry", "cannot assist", "refused"]):
                    logger.warning(f"OpenAI refusal detected. Response: {content[:200]}...")
                    # Include finish reason if available
                    finish_reason = completion.choices[0].finish_reason if hasattr(completion.choices[0], 'finish_reason') else None
                    if finish_reason:
                        logger.warning(f"Finish reason: {finish_reason}")

                # Parse JSON if schema was specified
                if schema and content:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as e:
                        msg = f"Failed to parse JSON response: {e}"
                        raise ValueError(msg) from e

                return content

        except Exception as e:
            error_str = str(e).lower()
            original_error = str(e)
            
            # Check for refusal messages
            if "refused" in error_str or "cannot assist" in error_str or "i'm sorry" in error_str:
                msg = f"OpenAI refused to respond: {original_error}"
                raise ValueError(msg) from e
            elif "api key" in error_str or "unauthorized" in error_str:
                msg = "OpenAI API key not configured or invalid"
                raise ValueError(msg) from e
            elif "model" in error_str and (
                "not found" in error_str
                or "does not exist" in error_str
                or "invalid" in error_str
            ):
                # Only treat as model error if it's specifically about model not found/invalid
                msg = f"Model '{model}' not supported or available"
                raise ValueError(msg) from e
            elif "rate limit" in error_str:
                msg = "OpenAI API rate limit exceeded"
                raise ValueError(msg) from e
            elif "quota" in error_str:
                msg = "OpenAI API quota exceeded"
                raise ValueError(msg) from e
            elif "content policy" in error_str or "content_policy" in error_str:
                msg = f"OpenAI content policy violation: {original_error}"
                raise ValueError(msg) from e
            else:
                # Preserve the original error for debugging
                msg = f"OpenAI API error: {original_error}"
                raise ValueError(msg) from e

    def validate_model(self, model: str) -> bool:
        """Validate if the model name is supported"""
        return model in self.SUPPORTED_MODELS

    def get_supported_models(self) -> list[str]:
        """Get list of supported model names"""
        return self.SUPPORTED_MODELS.copy()
