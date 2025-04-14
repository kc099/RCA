import warnings
from passlib.context import CryptContext

# Suppress bcrypt warning about __about__ attribute
warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

# Configure password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Generate a hash from a password"""
    return pwd_context.hash(password)
