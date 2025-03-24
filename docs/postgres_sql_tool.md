# PostgreSQL SQL Tool for OpenManus

This document explains how to use the read-only PostgreSQL tool with the OpenManus MCP architecture.

## Overview

The PostgreSQL tool allows the OpenManus agent to execute read-only SQL queries against a PostgreSQL database. It integrates with the Model Context Protocol (MCP) architecture, making it compatible with `run_mcp.py`.

## Requirements

- PostgreSQL database (local or remote)
- `asyncpg` Python package (already added to requirements.txt)
- Basic knowledge of SQL queries

## Configuration

The PostgreSQL tool uses the following default connection parameters:

- Host: `localhost`
- Port: `5432`
- User: `postgres`
- Password: `""` (empty string)
- Database: `postgres`

To modify these defaults, you'll need to update the parameters when the tool is initialized in the MCP server.

## Usage

Once you've started OpenManus with the `run_mcp.py` script, you can use the PostgreSQL tool through natural language prompts.

### Example Queries

Here are some examples of how to use the tool:

1. List all tables in the database:
   ```
   Use the postgres_sql tool to run this query: SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'
   ```

2. Query data with a specific format:
   ```
   Use the postgres_sql tool to execute SELECT * FROM users LIMIT 10 and format the results as json
   ```

3. Get database statistics:
   ```
   Use the postgres_sql tool to get information about the database with SHOW server_version
   ```

## Security Considerations

- The tool is designed to be read-only, accepting only SELECT, EXPLAIN, and SHOW queries
- It has built-in validation to prevent destructive operations
- It limits the number of rows returned to prevent overwhelming the agent's context window
- Connection parameters should be properly secured in production environments

## Debugging

If you encounter issues with the PostgreSQL tool, check the following:

1. Ensure your PostgreSQL server is running
2. Verify connection parameters
3. Check database user permissions
4. Look for specific error messages in the OpenManus logs

## Advanced Usage

### Using Query Parameters

For safer SQL queries, you can use parameterized queries:

```
Use the postgres_sql tool to run SELECT * FROM users WHERE age > $1 with params [18]
```

### Output Formats

The tool supports three output formats:

- `table` (default): ASCII table format
- `json`: JSON array format
- `csv`: Comma-separated values format

Example:
```
Use the postgres_sql tool to query SELECT * FROM products LIMIT 5 with format=json
```
