# Get config values
import os


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = GROQ_API_KEY
SECRET_KEY = os.getenv("SECRET_KEY")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
EMBEDDINGS_DIR = os.getenv("EMBEDDINGS_DIR", "embeddings")
