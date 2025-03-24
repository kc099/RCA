# MySQL Read/Write Tool

The MySQL Read/Write Tool allows OpenManus to execute both read and write SQL queries against a remote MySQL database. This tool is integrated with the MCP architecture for seamless use through natural language prompts.

## Features

- **Full Read/Write Access**: Execute SELECT, INSERT, UPDATE, DELETE, CREATE, and other SQL operations
- **Multiple Output Formats**: Results can be formatted as tables, JSON, or CSV
- **Parameterized Queries**: Support for safe query parameterization to prevent SQL injection
- **Write Confirmation**: Safety mechanism requiring explicit confirmation for write operations
- **Connection Pooling**: Efficient database connections using connection pooling
- **Asynchronous Operation**: Non-blocking database operations using asyncio

## Configuration

The tool is pre-configured to connect to a remote MySQL database with the following parameters:

```python
host="68.178.150.182"  # GoDaddy MySQL server
port=3306              # MySQL default port
user="kc099"           # MySQL username
password="Roboworks23!" # MySQL password
database="testdata"    # MySQL database name
max_rows=100           # Maximum rows to return
```

These parameters can be adjusted in the `app/mcp/server.py` file if needed.

## Usage Examples

### Read Operations

1. **Basic SELECT query**:
   ```
   Use the mysql_rw tool to execute SELECT * FROM users LIMIT 10
   ```

2. **Formatted output**:
   ```
   Use the mysql_rw tool to execute SELECT id, name, email FROM customers LIMIT 5 with format=json
   ```

3. **Parameterized query**:
   ```
   Use the mysql_rw tool to execute SELECT * FROM products WHERE category = %s with params=["electronics"]
   ```

### Write Operations

Write operations require explicit confirmation by setting `confirm_write=True`:

1. **Insert data**:
   ```
   Use the mysql_rw tool to execute INSERT INTO users (name, email) VALUES (%s, %s) with params=["John Doe", "john@example.com"], confirm_write=True
   ```

2. **Update data**:
   ```
   Use the mysql_rw tool to execute UPDATE products SET price = %s WHERE id = %s with params=[29.99, 123], confirm_write=True
   ```

3. **Create table**:
   ```
   Use the mysql_rw tool to execute CREATE TABLE IF NOT EXISTS customers (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100), email VARCHAR(100)) with confirm_write=True
   ```

## Security Considerations

- The tool requires explicit confirmation for write operations to prevent accidental data modification
- Use parameterized queries whenever possible to prevent SQL injection attacks
- Connection credentials are stored in the server code - consider using environment variables for production use
- The tool has full read/write access to the database, so be careful with the queries you execute

## Debugging

If you encounter issues with the MySQL tool, check the following:

1. Ensure network connectivity to the remote MySQL server
2. Verify connection parameters (host, port, user, password, database)
3. Check database user permissions
4. Look for specific error messages in the OpenManus logs

## Advanced Usage

### Transaction Support

For operations that require transactions, you can execute multiple queries in sequence:

```
Use the mysql_rw tool to execute BEGIN with confirm_write=True
Use the mysql_rw tool to execute INSERT INTO orders (customer_id, total) VALUES (%s, %s) with params=[42, 99.99], confirm_write=True
Use the mysql_rw tool to execute INSERT INTO order_items (order_id, product_id, quantity) VALUES (LAST_INSERT_ID(), %s, %s) with params=[123, 2], confirm_write=True
Use the mysql_rw tool to execute COMMIT with confirm_write=True
```

### Error Handling

The tool will return detailed error messages if a query fails. You can use these messages to diagnose and fix issues with your queries.
