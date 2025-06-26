"""HTTP node executor implementation"""

from typing import Any

import httpx
from jinja2 import Template
from pydantic import ValidationError

from seriesoftubes.config import get_config
from seriesoftubes.models import HTTPNodeConfig, Node
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import HTTPNodeInput, HTTPNodeOutput

# HTTP status codes
HTTP_ERROR_THRESHOLD = 400


class HTTPNodeExecutor(NodeExecutor):
    """Executor for HTTP nodes"""

    input_schema_class = HTTPNodeInput
    output_schema_class = HTTPNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute an HTTP node"""
        if not isinstance(node.config, HTTPNodeConfig):
            return NodeResult(
                output=None,
                success=False,
                error=f"Invalid config type for HTTP node: {type(node.config)}",
            )

        config = node.config
        app_config = get_config()

        try:
            # Prepare request components with template rendering
            context_data = self.prepare_context_data(node, context)

            # Render URL
            url = self._render_template(config.url, context_data)

            # Prepare headers
            headers = {}
            if config.headers:
                for key, value in config.headers.items():
                    headers[key] = self._render_template(value, context_data)

            # Prepare params
            params = None
            if config.params:
                params = {}
                for key, value in config.params.items():
                    params[key] = self._render_template_value(value, context_data)

            # Prepare body
            body = None
            if config.body:
                # Render each value in the dict body
                body = {}
                for key, value in config.body.items():
                    body[key] = self._render_template_value(value, context_data)

            # Always validate input when schema is defined
            input_data = {
                "url": url,
                "method": config.method.value,
                "headers": headers,
                "params": params or {},
                "body": body,
            }
            
            try:
                validated_input = self.validate_input(input_data)
                url = validated_input["url"]
                headers = validated_input["headers"]
                params = validated_input.get("params", {})
                body = validated_input.get("body")
            except ValidationError as e:
                # Format validation errors for clarity
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")
                
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Input validation failed for node '{node.name}':\n" + "\n".join(error_details),
                )

            # Set timeout
            timeout = config.timeout or app_config.http.timeout

            # Make request
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=config.method.value,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body,
                )

                # Handle response
                if response.status_code >= HTTP_ERROR_THRESHOLD:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}",
                        metadata={"status_code": response.status_code},
                    )

                # Try to parse JSON response
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text

                # Structure the output
                output = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "url": str(response.url),
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
                        error=f"Output validation failed for node '{node.name}':\n" + "\n".join(error_details),
                    )

                return NodeResult(
                    output=output,
                    success=True,
                    metadata={"status_code": response.status_code},
                )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=str(e),
            )

    def _render_template(self, template_str: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template string"""
        template = Template(template_str)
        return template.render(**context)

    def _render_template_value(self, value: Any, context: dict[str, Any]) -> Any:
        """Render a template value (could be string or other type)"""
        if isinstance(value, str):
            return self._render_template(value, context)
        return value
