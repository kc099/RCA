"""MySQL read/write tool for OpenManus.

This tool allows the agent to execute both read and write SQL queries against a remote MySQL database.
It integrates with the MCP architecture for seamless use through run_mcp.py.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Union

import aiomysql

from app.logger import logger
from app.tool.base import BaseTool, ToolResult


class MySQLRWTool(BaseTool):
    """Tool for executing read and write SQL queries against a MySQL database."""

    name: str = "mysql_rw"
    description: str = "Execute SQL queries (both read and write) against a MySQL database."
    
    # Connection parameters
    _connection_pool: Optional[aiomysql.Pool] = None
    _connection_params: Dict[str, Any] = {}
    _max_rows: int = 100  # Maximum number of rows to return
    
    async def initialize(
        self,
        host: str = "68.178.150.182",
        port: int = 3306,
        user: str = "kc099",
        password: str = "Roboworks23!",
        database: str = "testdata",
        max_rows: int = 100,
    ) -> None:
        """Initialize the connection pool to the MySQL database.
        
        Args:
            host: Database server hostname
            port: Database server port
            user: Database username
            password: Database password
            database: Database name
            max_rows: Maximum number of rows to return per query
        """
        self._connection_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "max_rows": max_rows
        }
        self._max_rows = max_rows
        
        # Create connection pool
        try:
            logger.info(f"Connecting to MySQL at {host}:{port}, database: {database}, user: {user}")
            
            # Store connection parameters with the correct key names for aiomysql
            connection_params = {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "db": database,  # aiomysql uses 'db' for the database name
                "autocommit": True,  # Enable autocommit for immediate writes
            }
            
            # Store our own version with the parameter names matching our initialize method
            self._connection_params = {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": database,
                "max_rows": max_rows
            }
            
            self._connection_pool = await aiomysql.create_pool(**connection_params)
            
            # Test connection by executing a simple query
            async with self._connection_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT VERSION()")
                    version = await cursor.fetchone()
                    logger.info(f"Successfully connected to MySQL: {version[0]}")
                
            return ToolResult(output=f"Successfully connected to MySQL at {host}:{port}")
        except Exception as e:
            error_msg = f"Failed to connect to MySQL: {str(e)}"
            logger.error(error_msg)
            self._connection_pool = None
            return ToolResult(error=error_msg)
    
    async def execute(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        format: Optional[str] = None,
        confirm_write: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Execute a SQL query against the MySQL database.

        Args:
            query: The SQL query to execute.
            params: Optional parameters for the query.
            format: Optional output format (table, json, csv).
            confirm_write: If True, confirm before executing write queries.

        Returns:
            Dict with query results or error message.
        """
        # Check if connection pool exists and reconnect if needed
        if not self._connection_pool or self._connection_pool.closed:
            try:
                logger.info("MySQL connection pool closed or not initialized. Reconnecting...")
                # Extract the parameters needed for aiomysql.create_pool
                connection_params = {
                    "host": self._connection_params["host"],
                    "port": self._connection_params["port"],
                    "user": self._connection_params["user"],
                    "password": self._connection_params["password"],
                    "db": self._connection_params["database"],  # aiomysql uses 'db' for database name
                    "autocommit": True
                }
                # Create a new connection pool
                self._connection_pool = await aiomysql.create_pool(**connection_params)
                logger.info(f"Successfully reconnected to MySQL at {connection_params['host']}:{connection_params['port']}")
            except Exception as e:
                logger.error(f"Failed to reconnect to MySQL: {str(e)}")
                return {"error": f"Error reconnecting to MySQL: {str(e)}"}

        # Validate the query if it's a write operation
        if self._is_write_query(query):
            if confirm_write is not True:
                return {"error": "Write operations require explicit confirmation. Set confirm_write=True to proceed."}

        try:
            # Use a timeout to prevent hanging connections
            conn = await asyncio.wait_for(self._connection_pool.acquire(), timeout=5.0)
            try:
                cursor = await conn.cursor(aiomysql.DictCursor)
                try:
                    # Execute the query with parameters if provided
                    if params:
                        await cursor.execute(query, params)
                    else:
                        await cursor.execute(query)

                    # For SELECT queries, fetch the results
                    if query.strip().upper().startswith("SELECT") or query.strip().upper().startswith("SHOW"):
                        # Fetch all rows (limited by max_rows)
                        rows = await cursor.fetchmany(self._max_rows)
                        
                        # Format the results based on the requested format
                        result = self._format_results(rows, format)
                        await cursor.close()
                        self._connection_pool.release(conn)
                        return result
                    else:
                        # For non-SELECT queries, return affected row count
                        result = {"message": f"Query executed successfully. Affected rows: {cursor.rowcount}"}
                        await cursor.close()
                        self._connection_pool.release(conn)
                        return result
                except Exception as e:
                    await cursor.close()
                    raise e
            except Exception as e:
                self._connection_pool.release(conn)
                raise e
        except asyncio.TimeoutError:
            logger.error("Timeout acquiring MySQL connection")
            # Reset connection pool for next attempt
            self._connection_pool = None
            return {"error": "Timeout acquiring MySQL connection. Please try again."}
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
    
    def _is_write_query(self, query: str) -> bool:
        """Check if a query is a write operation.
        
        Args:
            query: SQL query to check
            
        Returns:
            True if the query is a write operation, False otherwise
        """
        write_prefixes = ["insert ", "update ", "delete ", "drop ", "create ", "alter ", "truncate "]
        return any(query.startswith(prefix) for prefix in write_prefixes)
    
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
            return {"output": json.dumps(rows, indent=2, default=str)}
        elif format == "csv":
            result = ",".join(columns) + "\n"
            for row in rows:
                values = []
                for col in columns:
                    value = row.get(col, "")
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
                    val = row.get(col, "")
                    col_widths[col] = max(col_widths[col], len(str(val) if val is not None else "NULL"))
            
            # Create header
            header = "| " + " | ".join(str(col).ljust(col_widths[col]) for col in columns) + " |"
            separator = "+-" + "-+-".join("-" * col_widths[col] for col in columns) + "-+"
            
            # Create rows
            result_rows = []
            for row in rows:
                formatted_row = "| " + " | ".join(
                    str(row.get(col, "") if row.get(col, "") is not None else "NULL").ljust(col_widths[col]) 
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
                logger.info("Closed MySQL connection pool")
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    # This can happen during shutdown, just log and continue
                    logger.info("Event loop already closed during MySQL cleanup")
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
                            "description": "SQL query to execute",
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
                        "confirm_write": {
                            "type": "boolean",
                            "description": "Set to True to confirm execution of write operations",
                        },
                    },
                    "required": ["query"],
                },
            },
        }
