# Graceful Shutdown and Resource Management

This document describes the patterns and techniques used in RCA for graceful shutdown and resource management, particularly for asynchronous database connections.

## Table of Contents

- [Overview](#overview)
- [Common Issues with Asyncio Resources](#common-issues-with-asyncio-resources)
- [Solution Patterns](#solution-patterns)
  - [Explicit Cleanup](#explicit-cleanup)
  - [Error Handling in Cleanup Methods](#error-handling-in-cleanup-methods)
  - [Monkey Patching](#monkey-patching)
  - [Decorator Pattern for Safe Cleanup](#decorator-pattern-for-safe-cleanup)
- [Implementation in RCA](#implementation-in-rca)
- [Best Practices](#best-practices)

## Overview

Proper resource management is critical for any application, especially those using asynchronous I/O and database connections. When an application shuts down, it needs to clean up resources in an orderly fashion to prevent:

- Resource leaks
- Data corruption
- Error messages during shutdown
- Hanging connections

The RCA framework implements several patterns to ensure graceful shutdown and proper resource management.

## Common Issues with Asyncio Resources

### Event Loop Closed Errors

One of the most common issues with asyncio applications is the "Event loop is closed" error, which occurs when:

1. The application begins shutting down
2. The event loop is closed
3. Garbage collection tries to clean up resources that require an active event loop

This typically manifests as an error like:

```
RuntimeError: Event loop is closed
```

This error often appears in `__del__` methods of connection objects during garbage collection.

### Resource Cleanup Order

Another common issue is the order of resource cleanup. If resources are not cleaned up in the correct order, it can lead to errors or resource leaks.

## Solution Patterns

### Explicit Cleanup

The most important pattern is explicit cleanup, where resources are explicitly closed before the event loop is closed:

```python
async def cleanup_resources(self):
    """Clean up resources when shutting down."""
    # Close database connections first
    if hasattr(self, "db_connection") and self.db_connection:
        await self.db_connection.close()

    # Then close other resources
    # ...
```

### Error Handling in Cleanup Methods

Cleanup methods should handle errors gracefully, especially "Event loop is closed" errors:

```python
async def cleanup(self):
    """Clean up resources."""
    if self._connection_pool:
        try:
            self._connection_pool.close()
            await self._connection_pool.wait_closed()
            self._connection_pool = None
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                # This can happen during shutdown, just log and continue
                logger.info("Event loop already closed during cleanup")
                self._connection_pool = None
            else:
                raise
```

### Monkey Patching

For third-party libraries that don't handle cleanup gracefully, monkey patching can be used:

```python
def patch_connection_class():
    """Patch a connection class to handle event loop closed errors."""
    # Save the original __del__ method
    original_del = Connection.__del__

    # Define a new __del__ method that handles event loop closed errors
    def safe_del(self):
        try:
            original_del(self)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                # This happens during shutdown, just ignore it
                pass
            else:
                # Log other errors but don't crash
                logger.error(f"Error in Connection.__del__: {str(e)}")

    # Replace the original __del__ method with our safe version
    Connection.__del__ = safe_del
```

### Decorator Pattern for Safe Cleanup

A decorator can be used to wrap cleanup methods and handle errors consistently:

```python
def safe_db_cleanup(cleanup_func):
    """Decorator to safely handle database cleanup operations."""
    @functools.wraps(cleanup_func)
    async def wrapper(*args, **kwargs):
        try:
            return await cleanup_func(*args, **kwargs)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.info(f"Event loop already closed during cleanup: {str(e)}")
                return None
            else:
                raise

    return wrapper
```

## Implementation in OpenManus

OpenManus implements these patterns in several components:

### 1. MCPServer Cleanup

The `MCPServer` class implements a `cleanup_resources` method that is called in a `finally` block to ensure it runs even if an error occurs:

```python
def run(self, transport: str = "stdio") -> None:
    """Run the MCP server."""
    try:
        # Run the register_all_tools method in an asyncio event loop
        asyncio.run(self.register_all_tools())

        if transport == "stdio":
            logger.info("Starting OpenManus server (stdio mode)")
            self.stdio_transport.run()
        else:
            raise ValueError(f"Unsupported transport: {transport}")
    except Exception as e:
        logger.error(f"Error running MCP server: {str(e)}")
    finally:
        # Ensure proper cleanup of resources
        asyncio.run(self.cleanup_resources())
```

### 2. Database Tool Cleanup

The database tools (`PostgreSQLTool` and `MySQLRWTool`) implement cleanup methods that handle errors gracefully:

```python
async def cleanup(self) -> None:
    """Clean up resources when tool is no longer needed."""
    if self._connection_pool:
        try:
            self._connection_pool.close()
            await self._connection_pool.wait_closed()
            self._connection_pool = None
            logger.info("Closed connection pool")
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                # This can happen during shutdown, just log and continue
                logger.info("Event loop already closed during cleanup")
                self._connection_pool = None
            else:
                raise
```

### 3. Database Utilities

The `db_utils.py` module provides utilities for safely handling database cleanup operations:

- `safe_db_cleanup` decorator for wrapping cleanup methods
- `patch_aiomysql_connection` function to patch the aiomysql Connection class
- `patch_asyncpg_connection` function to patch the asyncpg Connection class

## Best Practices

1. **Always implement explicit cleanup methods** for classes that manage resources
2. **Call cleanup methods in a finally block** to ensure they run even if an error occurs
3. **Handle "Event loop is closed" errors gracefully** in cleanup methods
4. **Use a consistent pattern** for resource cleanup across the codebase
5. **Log cleanup operations** to help with debugging
6. **Clean up resources in the correct order** (e.g., close database connections before closing the event loop)
7. **Consider using monkey patching** for third-party libraries that don't handle cleanup gracefully
8. **Use decorators** to standardize error handling in cleanup methods

By following these patterns and best practices, OpenManus ensures graceful shutdown and proper resource management, preventing resource leaks and error messages during shutdown.
