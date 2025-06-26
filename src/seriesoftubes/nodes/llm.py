"""LLM node executor implementation"""

import json
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Template
from pydantic import ValidationError

from seriesoftubes.config import get_config
from seriesoftubes.models import LLMNodeConfig, Node
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import LLMNodeInput, LLMNodeOutput


class LLMNodeExecutor(NodeExecutor):
    """Executor for LLM nodes"""

    input_schema_class = LLMNodeInput
    output_schema_class = LLMNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute an LLM node"""
        if not isinstance(node.config, LLMNodeConfig):
            return NodeResult(
                output=None,
                success=False,
                error=f"Invalid config type for LLM node: {type(node.config)}",
            )

        config = node.config
        app_config = get_config()

        try:
            # Prepare prompt
            prompt = self._prepare_prompt(config, context, node)

            # Prepare and validate input
            context_data = self.prepare_context_data(node, context)
            input_data = {"prompt": prompt, "context_data": context_data}

            # Always validate input when schema is defined
            try:
                validated_input = self.validate_input(input_data)
                prompt = validated_input.get("prompt", prompt)
            except ValidationError as e:
                # Format validation errors for clarity
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")

                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Input validation failed for node '{node.name}':\n"
                    + "\n".join(error_details),
                )

            # Get model and temperature
            model = config.model or app_config.llm.model
            temperature = config.temperature or app_config.llm.temperature

            # Make API call based on provider
            if app_config.llm.provider == "openai":
                content = await self._call_openai(
                    prompt,
                    model,
                    temperature,
                    config.schema_definition,
                    app_config.llm.api_key,
                )
            elif app_config.llm.provider == "anthropic":
                content = await self._call_anthropic(
                    prompt,
                    model,
                    temperature,
                    config.schema_definition,
                    app_config.llm.api_key,
                )
            else:
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Unsupported LLM provider: {app_config.llm.provider}",
                )

            # Structure the output
            output = {
                "response": (
                    content if isinstance(content, str) else json.dumps(content)
                ),
                "structured_output": content if isinstance(content, dict) else None,
                "model_used": model,
                "token_usage": None,  # TODO: Extract from API responses
            }

            # Always validate output when schema is defined
            try:
                output = self.validate_output(output)
            except ValidationError as e:
                # Format validation errors for clarity
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")

                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Output validation failed for node '{node.name}':\n"
                    + "\n".join(error_details),
                )

            return NodeResult(output=output, success=True)

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=str(e),
            )

    def _prepare_prompt(
        self, config: LLMNodeConfig, context: NodeContext, node: Node
    ) -> str:
        """Prepare the prompt by rendering templates"""
        if config.prompt:
            prompt_text = config.prompt
        elif config.prompt_template:
            # Load template from file
            template_path = Path(config.prompt_template)
            if not template_path.exists():
                msg = f"Template file not found: {config.prompt_template}"
                raise ValueError(msg)
            prompt_text = template_path.read_text()
        else:
            msg = "No prompt or prompt_template specified"
            raise ValueError(msg)

        # Render template with context
        template = Template(prompt_text)
        context_data = self.prepare_context_data(node, context)
        return template.render(**context_data)

    async def _call_openai(
        self,
        prompt: str,
        model: str,
        temperature: float,
        schema: dict[str, Any] | None,
        api_key: str | None,
    ) -> Any:
        """Call OpenAI API"""
        if not api_key:
            msg = "OpenAI API key not configured"
            raise ValueError(msg)

        async with httpx.AsyncClient() as client:
            messages = [{"role": "user", "content": prompt}]

            request_data = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }

            # Add JSON mode if schema is specified
            if schema:
                request_data["response_format"] = {"type": "json_object"}
                messages[0]["content"] += "\n\nRespond with valid JSON."

            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Parse JSON if schema was specified
            if schema:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Return raw content if JSON parsing fails
                    return content

            return content

    async def _call_anthropic(
        self,
        prompt: str,
        model: str,
        temperature: float,
        schema: dict[str, Any] | None,
        api_key: str | None,
    ) -> Any:
        """Call Anthropic API"""
        if not api_key:
            msg = "Anthropic API key not configured"
            raise ValueError(msg)

        async with httpx.AsyncClient() as client:
            request_data: dict[str, Any] = {
                "model": model,
                "max_tokens": 4096,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            # Add JSON instructions if schema is specified
            if schema:
                messages = request_data["messages"]
                messages[0]["content"] += "\n\nRespond with valid JSON."

            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            response.raise_for_status()

            result = response.json()
            content = result["content"][0]["text"]

            # Parse JSON if schema was specified
            if schema:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Return raw content if JSON parsing fails
                    return content

            return content
