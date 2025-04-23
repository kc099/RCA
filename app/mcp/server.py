import logging
import asyncio
import sys
import inspect
import uuid
from typing import Dict, Any, Callable, Coroutine

# Configure logging - minimal and clean
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

import argparse
import atexit
import json
from inspect import Parameter, Signature
from typing import Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

import argparse
import asyncio
import atexit
import json
from inspect import Parameter, Signature
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from app.logger import logger
from app.tool.base import BaseTool
from app.resource.base import BaseResource
from app.tool.bash import Bash
from app.tool.browser_use_tool import BrowserUseTool
from app.tool.ask_human import AskHuman
from app.tool.mysql_rw import MySQLRWTool
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.python_execute import PythonExecute
from app.tool.terminate import Terminate
from app.tool.db_utils import patch_aiomysql_connection, patch_asyncpg_connection
from app.resource.postgres_data import PostgreSQLResource
from app.tool.file_saver import FileSaver
from app.tool.dashboard_viz import DashboardVizTool

# Patch database connections to handle event loop closed errors
patch_aiomysql_connection()
patch_asyncpg_connection()

# Import task_manager for the task_events function
import importlib.util
import sys

# Create logger
logger = logging.getLogger(__name__)

# Workaround to import task_manager from app.py without circular imports
def get_task_manager():
    try:
        # First try the direct import approach
        from app import task_manager
        return task_manager
    except (ImportError, AttributeError):
        # If that fails, use a more robust approach
        logger.info("Using dynamic import for task_manager")
        try:
            import sys
            import os
            # Get the project root directory
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            sys.path.insert(0, root_dir)
            # Dynamically import from app.py
            from app import task_manager
            return task_manager
        except Exception as e:
            logger.error(f"Failed to import task_manager: {e}")
            # Return a placeholder that will raise appropriate errors when used
            class MissingTaskManager:
                def __getattr__(self, name):
                    raise RuntimeError("task_manager could not be imported")
            return MissingTaskManager()

# Get the task_manager instance
task_manager = get_task_manager()

class MCPServer:
    """MCP Server implementation with tool and resource registration and management."""

    def __init__(self, name: str = "openmanus"):
        self.server = FastMCP(name)
        self.tools: Dict[str, BaseTool] = {}
        self.resources: Dict[str, BaseResource] = {}

        # Initialize standard tools
        self.tools["bash"] = Bash()
        self.tools["browser"] = BrowserUseTool()
        self.tools["ask_human"] = AskHuman()
        self.tools["editor"] = StrReplaceEditor()
        self.tools["mysql_rw"] = MySQLRWTool()
        self.tools["terminate"] = Terminate()
        self.tools["file_saver"] = FileSaver()
        self.tools["dashboard_viz"] = DashboardVizTool()

    def register_tool(self, tool: BaseTool, method_name: Optional[str] = None) -> None:
        """Register a tool with parameter validation and documentation."""
        tool_name = method_name or tool.name
        tool_param = tool.to_param()
        tool_function = tool_param["function"]

        # Define the async function to be registered
        async def tool_method(**kwargs):
            logger.info(f"Executing {tool_name}: {kwargs}")
            result = await tool.execute(**kwargs)

            logger.info(f"Result of {tool_name}: {result}")

            # Format the result for better UI rendering, especially for MySQL outputs
            if tool_name == "mysql_rw" and isinstance(result, dict) and "output" in result:
                # Generate a unique ID for this tool result to avoid duplication in UI
                result["id"] = str(uuid.uuid4())
                # Ensure proper formatting for visualization
                if isinstance(result["output"], str) and ("+-" in result["output"] and "-+" in result["output"]):
                    result["visualization_type"] = "table"

            # Handle different types of results (match original logic)
            if hasattr(result, "model_dump"):
                return json.dumps(result.model_dump())
            elif isinstance(result, dict):
                return json.dumps(result)
            return result

        # Set method metadata
        tool_method.__name__ = tool_name
        tool_method.__doc__ = self._build_docstring(tool_function)
        tool_method.__signature__ = self._build_signature(tool_function)

        # Store parameter schema (important for tools that access it programmatically)
        param_props = tool_function.get("parameters", {}).get("properties", {})
        required_params = tool_function.get("parameters", {}).get("required", [])
        tool_method._parameter_schema = {
            param_name: {
                "description": param_details.get("description", ""),
                "type": param_details.get("type", "any"),
                "required": param_name in required_params,
            }
            for param_name, param_details in param_props.items()
        }

        # Register with server
        self.server.tool()(tool_method)
        logger.info(f"Registered tool: {tool_name}")

    def register_resource(self, resource: BaseResource, method_name: Optional[str] = None) -> None:
        """Register a resource with parameter validation and documentation."""
        resource_name = method_name or resource.name
        self.resources[resource_name] = resource

        # Prepare function info for documentation
        resource_function = {
            "name": resource_name,
            "description": resource.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }

        # Create a wrapper function that validates and passes parameters to the resource
        async def resource_method(**kwargs):
            """Resource method wrapper."""
            try:
                result = await resource.access(**kwargs)
                return result
            except Exception as e:
                logger.exception(f"Error executing resource {resource_name}: {e}")
                return {"error": str(e)}

        # Handle various return types
        def serialize_result(result):
            """Serialize the result to JSON if possible."""
            if hasattr(result, "model_dump"):
                return json.dumps(result.model_dump())
            elif isinstance(result, dict):
                return json.dumps(result)
            return result

        # Set method metadata
        resource_method.__name__ = resource_name
        resource_method.__doc__ = self._build_docstring(resource_function)
        resource_method.__signature__ = self._build_signature(resource_function)

        # Store parameter schema
        param_props = resource_function.get("parameters", {}).get("properties", {})
        required_params = resource_function.get("parameters", {}).get("required", [])
        resource_method._parameter_schema = {
            param_name: {
                "description": param_details.get("description", ""),
                "type": param_details.get("type", "any"),
                "required": param_name in required_params,
            }
            for param_name, param_details in param_props.items()
        }

        # Register with server using proper resource format with URI
        # FastMCP expects a valid URL, using http://resources/ prefix
        resource_uri = f"http://resources/{resource_name}"
        self.server.resource(resource_uri)(resource_method)
        logger.info(f"Registered resource: {resource_name} with URI: {resource_uri}")

    def _build_docstring(self, tool_function: dict) -> str:
        """Build a formatted docstring from tool function metadata."""
        description = tool_function.get("description", "")
        param_props = tool_function.get("parameters", {}).get("properties", {})
        required_params = tool_function.get("parameters", {}).get("required", [])

        # Build docstring (match original format)
        docstring = description
        if param_props:
            docstring += "\n\nParameters:\n"
            for param_name, param_details in param_props.items():
                required_str = (
                    "(required)" if param_name in required_params else "(optional)"
                )
                param_type = param_details.get("type", "any")
                param_desc = param_details.get("description", "")
                docstring += (
                    f"    {param_name} ({param_type}) {required_str}: {param_desc}\n"
                )

        return docstring

    def _build_signature(self, tool_function: dict) -> Signature:
        """Build a function signature from tool function metadata."""
        param_props = tool_function.get("parameters", {}).get("properties", {})
        required_params = tool_function.get("parameters", {}).get("required", [])

        parameters = []

        # Follow original type mapping
        for param_name, param_details in param_props.items():
            param_type = param_details.get("type", "")
            default = Parameter.empty if param_name in required_params else None

            # Map JSON Schema types to Python types (same as original)
            annotation = Any
            if param_type == "string":
                annotation = str
            elif param_type == "integer":
                annotation = int
            elif param_type == "number":
                annotation = float
            elif param_type == "boolean":
                annotation = bool
            elif param_type == "object":
                annotation = dict
            elif param_type == "array":
                annotation = list

            # Create parameter with same structure as original
            param = Parameter(
                name=param_name,
                kind=Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
            parameters.append(param)

        return Signature(parameters=parameters)

    async def cleanup(self) -> None:
        """Clean up server resources."""
        logger.info("Cleaning up resources")
        # Follow original cleanup logic - only clean browser tool
        if "browser" in self.tools and hasattr(self.tools["browser"], "cleanup"):
            await self.tools["browser"].cleanup()

    async def register_all_tools(self) -> None:
        """Register all tools with the server."""
        # Initialize tools
        browser_use_tool = BrowserUseTool()
        mysql_rw_tool = MySQLRWTool()
        python_tool = PythonExecute()
        terminate_tool = Terminate()
        string_tool = StrReplaceEditor()
        file_saver_tool = FileSaver()
        ask_human_tool = AskHuman()
        dashboard_viz_tool = DashboardVizTool()

        # Register tools with the agent
        self.register_tool(browser_use_tool)
        self.register_tool(mysql_rw_tool)
        self.register_tool(python_tool)
        self.register_tool(terminate_tool)
        self.register_tool(string_tool)
        self.register_tool(file_saver_tool)
        #self.register_tool(ask_human_tool)
        self.register_tool(dashboard_viz_tool)

        # Initialize MySQL read/write tool with remote connection parameters
        await mysql_rw_tool.initialize(
            host="68.178.150.182",  # GoDaddy MySQL server
            port=3306,  # MySQL default port
            user="kc099",  # MySQL username
            password="Roboworks23!",  # MySQL password
            database="testdata",  # MySQL database name
            max_rows=100
        )

        # Initialize and register resources
        await self.register_all_resources()

    async def register_all_resources(self) -> None:
        """Register all resources with the server."""
        # Initialize resources
        # postgres_resource = PostgreSQLResource()

        # # Register resources with the agent
        # self.register_resource(postgres_resource)

        # # Initialize PostgreSQL resource
        # await postgres_resource.initialize(
        #     host="127.0.0.1",
        #     port=5432,  # Default PostgreSQL port, adjust if needed
        #     user="postgres",  # Default PostgreSQL user, adjust if needed
        #     password="12345",  # Password for PostgreSQL
        #     database="postgres",  # Default database name, adjust if needed
        #     max_rows=100
        # )

    async def cleanup_resources(self) -> None:
        """Clean up resources when the server is shutting down."""
        logger.info("Cleaning up server resources...")

        # Close database connections first
        try:
            # Clean up MySQL connection if it exists
            if "mysql_rw" in self.tools and hasattr(self.tools["mysql_rw"], "cleanup"):
                logger.info("Closing MySQL connection...")
                await self.tools["mysql_rw"].cleanup()

            # Clean up PostgreSQL connection if it exists
            if "postgres_data" in self.resources and hasattr(self.resources["postgres_data"], "cleanup"):
                logger.info("Closing PostgreSQL connection...")
                await self.resources["postgres_data"].cleanup()
        except Exception as e:
            logger.error(f"Error during database cleanup: {str(e)}")

        logger.info("Server resources cleaned up")

    def run(self, transport: str = "stdio") -> None:
        """Run the MCP server."""
        try:
            # Run the register_all_tools method in an asyncio event loop
            asyncio.run(self.register_all_tools())

            if transport == "stdio":
                logger.info("Starting OpenManus server (stdio mode)")
                self.server.run(transport=transport)
            else:
                raise ValueError(f"Unsupported transport: {transport}")
        except Exception as e:
            logger.error(f"Error running MCP server: {str(e)}")
        finally:
            # Ensure proper cleanup of resources
            asyncio.run(self.cleanup_resources())


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="OpenManus MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Communication method: stdio or http (default: stdio)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Create and run server (maintaining original flow)
    server = MCPServer()
    server.run(transport=args.transport)
