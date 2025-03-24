#!/usr/bin/env python
"""
Test script for PostgreSQL tool in OpenManus.
This script tests the connection to PostgreSQL and executes a simple query.
"""

import asyncio
import sys

from app.logger import logger
from app.tool.postgres_sql import PostgreSQLTool


async def test_postgres_connection():
    """Test PostgreSQL connection and execute a simple query."""
    # Create PostgreSQL tool instance
    postgres_tool = PostgreSQLTool()

    # Initialize with connection parameters
    # Adjust these parameters to match your PostgreSQL setup
    init_result = await postgres_tool.initialize(
        host="127.0.0.1",
        port=5432,  # Default PostgreSQL port
        user="postgres",  # Default PostgreSQL user
        password="12345",  # Password you mentioned was used with pgAdmin
        database="postgres",  # Default database name
        max_rows=100
    )

    if init_result and hasattr(init_result, 'error') and init_result.error:
        logger.error(f"Failed to initialize PostgreSQL connection: {init_result.error}")
        return False

    # Test queries with different output formats
    test_queries = [
        # Basic information queries
        ("SELECT version()", None, "table"),
        ("SELECT current_database()", None, "table"),

        # List all tables in the database
        ("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        """, None, "table"),

        # Test different output formats
        ("SELECT 1 as num, 'test' as text", None, "json"),
        ("SELECT 1 as num, 'test' as text", None, "csv"),
    ]

    # Execute each test query
    success = True
    for query, params, format in test_queries:
        logger.info(f"Executing query: {query[:50]}{'...' if len(query) > 50 else ''}")
        result = await postgres_tool.execute(query=query, params=params, format=format)

        if hasattr(result, 'error') and result.error:
            logger.error(f"Query failed: {result.error}")
            success = False
        else:
            logger.info(f"Query result ({format} format):\n{result.output}")
            print(f"\n--- Query Result ({format} format) ---\n{result.output}\n")

    # Clean up
    await postgres_tool.cleanup()
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(test_postgres_connection())
        if success:
            print("\n✅ PostgreSQL connection and queries successful!")
            sys.exit(0)
        else:
            print("\n❌ Some PostgreSQL tests failed. Check the logs for details.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error in test script: {str(e)}", exc_info=True)
        print(f"\n❌ Test failed with error: {str(e)}")
        sys.exit(1)
