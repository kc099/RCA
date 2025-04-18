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


def get_env_var(key: str, default: Any = None, required: bool = False) -> Any:
    """
    Get an environment variable or return a default value.
    
    Args:
        key: The name of the environment variable
        default: A default value to return if the environment variable is not set
        required: If True, raise an error when the variable is not set
    
    Returns:
        The value of the environment variable, or the default value
    
    Raises:
        ValueError: If the variable is required but not found
    """
    value = os.environ.get(key)
    if value is None:
        if required:
            raise ValueError(f"Required environment variable '{key}' is not set. Please check your .env file.")
        return default
    return value


def get_db_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables.
    
    Returns:
        A dictionary with database configuration parameters
    
    Raises:
        ValueError: If required database configuration variables are missing
    """
    import pymysql.cursors
    
    # Get required database connection parameters
    try:
        # These are required for database connection
        host = get_env_var('DB_HOST', required=True)
        user = get_env_var('DB_USER', required=True)
        password = get_env_var('DB_PASSWORD', required=True)
        database = get_env_var('DB_NAME', required=True)
        
        # These have safe defaults
        port = int(get_env_var('DB_PORT', 3306))
        charset = get_env_var('DB_CHARSET', 'utf8mb4')
        
        return {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database,
            'charset': charset,
            'cursorclass': pymysql.cursors.DictCursor
        }
    except ValueError as e:
        print(f"ERROR: Database configuration error: {str(e)}")
        print("Please ensure your .env file contains all required database configuration variables.")
        raise


def get_jwt_settings() -> Dict[str, Any]:
    """
    Get JWT configuration from environment variables.
    
    Returns:
        A dictionary with JWT configuration parameters
    """
    from secrets import token_hex
    
    try:
        # JWT secret is required for security
        jwt_secret = get_env_var('JWT_SECRET_KEY')
        if not jwt_secret:
            print("WARNING: No JWT_SECRET_KEY found in environment. Generating a random one for this session.")
            print("This is not recommended for production - set a persistent JWT_SECRET_KEY in your .env file.")
            jwt_secret = token_hex(32)
        
        # These have safe defaults
        algorithm = get_env_var('JWT_ALGORITHM', 'HS256')
        token_expire_minutes = int(get_env_var('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 30))
        
        return {
            'secret_key': jwt_secret,
            'algorithm': algorithm,
            'access_token_expire_minutes': token_expire_minutes
        }
    except Exception as e:
        print(f"ERROR: JWT configuration error: {str(e)}")
        print("JWT authentication may not work correctly. Check your .env file.")
        raise
