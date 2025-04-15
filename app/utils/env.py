"""
Environment variable utilities for loading and accessing environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


def get_env_var(key: str, default: Any = None) -> Any:
    """
    Get an environment variable or return a default value.

    Args:
        key: The name of the environment variable
        default: A default value to return if the environment variable is not set

    Returns:
        The value of the environment variable, or the default value
    """
    return os.environ.get(key, default)


def get_db_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables.

    Returns:
        A dictionary with database configuration parameters
    """
    import pymysql.cursors

    return {
        'host': get_env_var('DB_HOST', '68.178.150.182'),
        'port': int(get_env_var('DB_PORT', 3306)),
        'user': get_env_var('DB_USER', 'kc099'),
        'password': get_env_var('DB_PASSWORD', 'Roboworks23!'),
        'database': get_env_var('DB_NAME', 'auth'),
        'charset': get_env_var('DB_CHARSET', 'utf8mb4'),
        'cursorclass': pymysql.cursors.DictCursor
    }


def get_jwt_settings() -> Dict[str, Any]:
    """
    Get JWT configuration from environment variables.

    Returns:
        A dictionary with JWT configuration parameters
    """
    from secrets import token_hex

    # Generate a random secret key if one is not provided
    default_secret = token_hex(32)

    return {
        'secret_key': get_env_var('JWT_SECRET_KEY', default_secret),
        'algorithm': get_env_var('JWT_ALGORITHM', 'HS256'),
        'access_token_expire_minutes': int(get_env_var('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 30))
    }
