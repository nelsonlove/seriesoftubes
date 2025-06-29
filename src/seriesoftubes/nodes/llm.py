"""LLM node executor implementation"""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from seriesoftubes.config import get_config
from seriesoftubes.models import LLMNodeConfig, Node
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.providers import get_provider
from seriesoftubes.schemas import LLMNodeInput, LLMNodeOutput
from seriesoftubes.template_engine import TemplateSecurityLevel, render_template

logger = logging.getLogger(__name__)


class LLMNodeExecutor(NodeExecutor):
    """Executor for LLM nodes"""

    input_schema_class = LLMNodeInput
    output_schema_class = LLMNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute an LLM node"""
        logger.info(f"Executing LLM node: {node.name}")
        
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

            # Get provider and make API call
            try:
                provider = get_provider(app_config.llm.provider, app_config.llm.api_key)
                content = await provider.call(
                    prompt,
                    model,
                    temperature,
                    config.schema_definition,
                )
            except ValueError as e:
                return NodeResult(
                    output=None,
                    success=False,
                    error=str(e),
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

        # Render template with context using secure template engine
        context_data = self.prepare_context_data(node, context)
        # LLM prompts often need safe expressions for formatting
        return render_template(
            prompt_text, 
            context_data, 
            level=TemplateSecurityLevel.SAFE_EXPRESSIONS,
            node_type="llm"
        )
