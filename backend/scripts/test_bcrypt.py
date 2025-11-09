from passlib.context import CryptContext

ctx = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
print("sha256 available, hashing test:", ctx.hash("short_password_123"))
