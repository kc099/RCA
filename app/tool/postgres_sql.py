"""PostgreSQL read-only SQL tool for OpenManus.

This tool allows the agent to execute read-only SQL queries against a PostgreSQL database.
It integrates with the MCP architecture for seamless use through run_mcp.py.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Union

import asyncpg

from app.logger import logger
from app.tool.base import BaseTool, ToolResult


class PostgreSQLTool(BaseTool):
    """Tool for executing read-only SQL queries against a PostgreSQL database."""

    name: str = "postgres_sql"
    description: str = "Execute read-only SQL queries against a PostgreSQL database."

    # Connection parameters
    _connection_pool: Optional[asyncpg.Pool] = None
    _connection_params: Dict[str, Any] = {}
    _MAX_ROWS: int = 100  # Maximum number of rows to return

    async def initialize(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        database: str = "postgres",
        max_rows: int = 100,
    ) -> None:
        """Initialize the connection pool to the PostgreSQL database.
        
        Args:
            host: Database server hostname
            port: Database server port
            user: Database username
            password: Database password
            database: Database name
            max_rows: Maximum number of rows to return per query
        """
        # Store connection parameters for reconnection
        self._connection_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "max_rows": max_rows
        }
        
        # Create connection pool
        try:
            logger.info(f"Connecting to PostgreSQL at {host}:{port}, database: {database}, user: {user}")
            
            # Create connection pool with parameters expected by asyncpg
            connection_params = {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": database,  # asyncpg uses 'database' not 'db'
            }
            
            self._connection_pool = await asyncpg.create_pool(**connection_params)
            
            # Test connection by executing a simple query
            async with self._connection_pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"Successfully connected to PostgreSQL: {version}")
                
            return ToolResult(output=f"Successfully connected to PostgreSQL at {host}:{port}")
        except Exception as e:
            error_msg = f"Failed to connect to PostgreSQL: {str(e)}"
            logger.error(error_msg)
            self._connection_pool = None
            return ToolResult(error=error_msg)

    async def execute(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a read-only SQL query against the PostgreSQL database.

        Args:
            query: The SQL query to execute.
            params: Optional parameters for the query.
            format: Optional output format (table, json, csv).

        Returns:
            Dict with query results or error message.
        """
        # Check if connection pool exists and reconnect if needed
        if not self._connection_pool:
            try:
                logger.info("PostgreSQL connection pool not initialized. Reconnecting...")
                # Extract the parameters needed for asyncpg.create_pool
                connection_params = {
                    "host": self._connection_params["host"],
                    "port": self._connection_params["port"],
                    "user": self._connection_params["user"],
                    "password": self._connection_params["password"],
                    "database": self._connection_params["database"]
                }
                # Create a new connection pool
                self._connection_pool = await asyncpg.create_pool(**connection_params)
                logger.info(f"Successfully reconnected to PostgreSQL at {connection_params['host']}:{connection_params['port']}")
            except Exception as e:
                logger.error(f"Failed to reconnect to PostgreSQL: {str(e)}")
                return {"error": f"Error reconnecting to PostgreSQL: {str(e)}"}

        # Validate that this is a read-only query
        if not self._is_read_only_query(query):
            return {"error": "Only read-only queries (SELECT, EXPLAIN, SHOW) are allowed"}

        try:
            # Use a timeout to prevent hanging connections
            conn = await asyncio.wait_for(self._connection_pool.acquire(), timeout=5.0)
            try:
                # Execute the query with parameters if provided
                if params:
                    rows = await conn.fetch(query, *params)
                else:
                    rows = await conn.fetch(query)

                # Format the results based on the requested format
                result = self._format_results(rows, format)
                self._connection_pool.release(conn)
                return result
            except Exception as e:
                self._connection_pool.release(conn)
                raise e
        except asyncio.TimeoutError:
            logger.error("Timeout acquiring PostgreSQL connection")
            # Reset connection pool for next attempt
            self._connection_pool = None
            return {"error": "Timeout acquiring PostgreSQL connection. Please try again."}
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.error("Event loop is closed. Attempting to reconnect on next call...")
                # Reset connection pool
                self._connection_pool = None
                return {"error": f"Error executing query: {str(e)}. Please try again."}
            else:
                logger.error(f"RuntimeError executing query: {str(e)}")
                return {"error": f"Error executing query: {str(e)}"}
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return {"error": f"Error executing query: {str(e)}"}

    def _is_read_only_query(self, query: str) -> bool:
        """Check if a query is read-only.

        Args:
            query: SQL query to check

        Returns:
            True if the query is read-only, False otherwise
        """
        # Check if query starts with SELECT, EXPLAIN, or SHOW
        read_only_prefixes = ["select ", "explain ", "show "]
        return any(query.startswith(prefix) for prefix in read_only_prefixes)

    def _format_results(self, rows: List[Dict], format: Optional[str] = None) -> Dict[str, Any]:
        """Format query results based on the requested format."""
        if not rows:
            return {"message": "Query returned no results."}
            
        # Get column names from the first row
        if rows and len(rows) > 0:
            columns = list(rows[0].keys())
        else:
            columns = []
            
        if format == "json":
            # Convert rows to a list of dicts for JSON serialization
            json_rows = [dict(row) for row in rows]
            return {"output": json.dumps(json_rows, indent=2, default=str)}
        elif format == "csv":
            result = ",".join(columns) + "\n"
            for row in rows:
                values = []
                for col in columns:
                    value = row[col] if col in row else ""
                    # Quote strings containing commas
                    if isinstance(value, str) and "," in value:
                        value = f'"{value}"'
                    values.append(str(value) if value is not None else "")
                result += ",".join(values) + "\n"
            return {"output": result}
        else:  # Default to table format
            if not rows:
                return {"output": "Query returned no results."}
            
            # Determine column widths
            col_widths = {col: len(str(col)) for col in columns}
            for row in rows:
                for col in columns:
                    val = row[col] if col in row else ""
                    col_widths[col] = max(col_widths[col], len(str(val) if val is not None else "NULL"))
            
            # Create header
            header = "| " + " | ".join(str(col).ljust(col_widths[col]) for col in columns) + " |"
            separator = "+-" + "-+-".join("-" * col_widths[col] for col in columns) + "-+"
            
            # Create rows
            result_rows = []
            for row in rows:
                formatted_row = "| " + " | ".join(
                    str(row[col] if col in row else "NULL").ljust(col_widths[col]) 
                    for col in columns
                ) + " |"
                result_rows.append(formatted_row)
            
            return {"output": "\n".join([separator, header, separator] + result_rows + [separator])}

    async def cleanup(self) -> None:
        """Clean up resources when tool is no longer needed."""
        if self._connection_pool:
            try:
                self._connection_pool.close()
                await self._connection_pool.wait_closed()
                self._connection_pool = None
                logger.info("Closed PostgreSQL connection pool")
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    # This can happen during shutdown, just log and continue
                    logger.info("Event loop already closed during PostgreSQL cleanup")
                    self._connection_pool = None
                else:
                    raise

    def to_param(self) -> Dict[str, Any]:
        """Convert the tool to its parameter representation."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute (must be read-only SELECT, EXPLAIN, or SHOW)",
                        },
                        "params": {
                            "type": "array",
                            "items": {"type": "any"},
                            "description": "Optional parameters for the SQL query",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["table", "json", "csv"],
                            "description": "Output format (table, json, or csv)",
                        },
                    },
                    "required": ["query"],
                },
            },
        }
