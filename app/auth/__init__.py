"""Authentication module for the RCA application."""

# Fix the bcrypt warning by monkey patching the _bcrypt module
import warnings
import sys

# Suppress all bcrypt warnings
warnings.filterwarnings("ignore", message=".*bcrypt.*")

# Monkey patch the bcrypt module to fix the '__about__' attribute issue
import bcrypt
if not hasattr(bcrypt, '__about__'):
    # Create a mock __about__ module with version attribute
    class MockAbout:
        __version__ = getattr(bcrypt, '__version__', '4.0.0')
    
    # Add the mock module to bcrypt
    bcrypt.__about__ = MockAbout

# Import after fixing the warning
from app.auth.repository import create_initial_admin
