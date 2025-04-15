#!/usr/bin/env python
"""
Test script for MySQL read/write tool in OpenManus.
This script tests the connection to the remote MySQL database and executes sample queries.
"""

import asyncio
import sys

from app.logger import logger
from app.tool.mysql_rw import MySQLRWTool


async def test_mysql_connection():
    """Test MySQL connection and execute sample queries."""
    # Create MySQL tool instance
    mysql_tool = MySQLRWTool()

    # Initialize with connection parameters
    init_result = await mysql_tool.initialize(
        host="68.178.150.182",  # GoDaddy MySQL server
        port=3306,  # MySQL default port
        user="kc099",  # MySQL username
        password="Roboworks23!",  # MySQL password
        database="auth",  # MySQL database name
        max_rows=100
    )

    if init_result and hasattr(init_result, 'error') and init_result.error:
        logger.error(f"Failed to initialize MySQL connection: {init_result.error}")
        return False

    # Test queries with different output formats and operations
    test_queries = [
        # Basic information queries (read-only)
        ("SELECT VERSION()", None, "table", False),
        ("SELECT DATABASE()", None, "table", False),

        # List tables in the database (read-only)
        ("SHOW TABLES", None, "table", False),

        # Test different output formats (read-only)
        ("SELECT 1 as num, 'test' as text", None, "json", False),
        ("SELECT 1 as num, 'test' as text", None, "csv", False),

        # Test write operation (create a test table)
        ("""
        CREATE TABLE IF NOT EXISTS test_table (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """, None, "table", True),

        # Test insert operation
        ("INSERT INTO test_table (name) VALUES (%s)", ["Test entry from OpenManus"], "table", True),

        # Verify the inserted data
        ("SELECT * FROM test_table ORDER BY id DESC LIMIT 5", None, "table", False),
    ]

    # Execute each test query
    success = True
    for query, params, format, is_write in test_queries:
        logger.info(f"Executing query: {query[:50]}{'...' if len(query) > 50 else ''}")
        result = await mysql_tool.execute(
            query=query,
            params=params,
            format=format,
            confirm_write=is_write
        )

        if hasattr(result, 'error') and result.error:
            logger.error(f"Query failed: {result.error}")
            success = False
        else:
            logger.info(f"Query result ({format} format):\n{result.output}")
            print(f"\n--- Query Result ({format} format) ---\n{result.output}\n")

    # Clean up
    await mysql_tool.cleanup()
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(test_mysql_connection())
        if success:
            print("\n✅ MySQL connection and queries successful!")
            sys.exit(0)
        else:
            print("\n❌ Some MySQL tests failed. Check the logs for details.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error in test script: {str(e)}", exc_info=True)
        print(f"\n❌ Test failed with error: {str(e)}")
        sys.exit(1)
