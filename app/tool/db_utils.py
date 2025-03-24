"""Database utilities for OpenManus.

This module provides utility functions for working with database connections.
"""

import asyncio
import functools
import logging
import sys
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')

def safe_db_cleanup(cleanup_func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to safely handle database cleanup operations.
    
    This decorator catches and handles RuntimeError exceptions related to
    closed event loops, which can happen during application shutdown.
    
    Args:
        cleanup_func: The cleanup function to wrap
        
    Returns:
        Wrapped function that handles event loop errors gracefully
    """
    @functools.wraps(cleanup_func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await cleanup_func(*args, **kwargs)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.info(f"Event loop already closed during database cleanup: {str(e)}")
                return None  # type: ignore
            else:
                raise
    
    return wrapper


def patch_aiomysql_connection() -> None:
    """Patch aiomysql Connection to handle event loop closed errors.
    
    This function monkey patches the aiomysql Connection class to handle
    event loop closed errors during garbage collection.
    """
    try:
        import aiomysql
        
        # Save the original __del__ method
        original_del = aiomysql.Connection.__del__
        
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
        aiomysql.Connection.__del__ = safe_del
        
        logger.info("Successfully patched aiomysql Connection.__del__ method")
    except ImportError:
        logger.warning("aiomysql not installed, skipping patch")
    except Exception as e:
        logger.error(f"Failed to patch aiomysql Connection: {str(e)}")


def patch_asyncpg_connection() -> None:
    """Patch asyncpg Connection to handle event loop closed errors.
    
    This function monkey patches the asyncpg Connection class to handle
    event loop closed errors during garbage collection.
    """
    try:
        import asyncpg
        
        # Save the original __del__ method if it exists
        original_del = getattr(asyncpg.Connection, "__del__", None)
        
        if original_del:
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
            asyncpg.Connection.__del__ = safe_del
            
            logger.info("Successfully patched asyncpg Connection.__del__ method")
        else:
            logger.info("asyncpg Connection has no __del__ method, no patch needed")
    except ImportError:
        logger.warning("asyncpg not installed, skipping patch")
    except Exception as e:
        logger.error(f"Failed to patch asyncpg Connection: {str(e)}")
