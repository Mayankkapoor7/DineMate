import os, sqlite3
from dotenv import load_dotenv
from pathlib import Path
from pydantic import SecretStr
from scripts.logger import get_logger

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)

# Environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

TEMPERATURE = 0.1

# Static paths
DB_PATH = Path(__file__).parent.parent / "database" / "dinemate.db"
CHECKPOINTS_DB_PATH = Path(__file__).parent.parent / "database" / "checkpoints.db"

# langsmith configuration
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "DineMate")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

# Short term memory handling
SUMMARY_MESSAGE_THRESHOLD = 15         
KEEP_LAST_MESSAGES = 4                  

# Model configuration
DEFAULT_MODEL_NAME ='meta-llama/Llama-3.3-70B-Instruct'
LIGHTWEIGHT_MODEL='meta-llama/Llama-3.1-8B-Instruct'

# Prompt guard configuration
GUARDRAIL_MODEL_NAME ="gpt-oss-safeguard-20b"
GUARDRAIL_BLOCK_THRESHOLD = 0.5
GUARDRAIL_BORDERLINE_THRESHOLD = 0.4
GUARDRAIL_TIMEOUT_SECONDS = 1

def get_db_connection():
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        logger.info("Database connected")
        return conn
    except sqlite3.Error as e:
        logger.error({"error": str(e), "message": "Connection failed"})
        raise