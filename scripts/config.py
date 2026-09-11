import os
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

# langsmith configuration
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "DineMate")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

# Short term memory handling
SUMMARY_MESSAGE_THRESHOLD = 15         
KEEP_LAST_MESSAGES = 10                 

# Model configuration
DEFAULT_MODEL_NAME = 'openai/gpt-oss-120b'
LIGHTWEIGHT_MODEL = 'openai/gpt-oss-20b'
LIGHTWEIGHT_MODEL_NAME = LIGHTWEIGHT_MODEL

# Prompt guard configuration (outputs 0.0 to 1.0 probability of prompt injection / jailbreak)
GUARDRAIL_MODEL_NAME = "meta-llama/llama-prompt-guard-2-86m"
GUARDRAIL_BLOCK_THRESHOLD = 0.8
GUARDRAIL_BORDERLINE_THRESHOLD = 0.7
GUARDRAIL_TIMEOUT_SECONDS = 4

# MySQL configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3307))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "rootpassword")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "dinemate")
# Twilio Warm Transfer configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "+17372508034")
SUPPORT_PHONE_NUMBER = os.getenv("SUPPORT_PHONE_NUMBER", "+917906773761")
TWILIO_CALL_URL = os.getenv("TWILIO_CALL_URL", "https://webhooks.twilio.com/v1/Voice/Template/voice_speech_recognition")

# Razorpay Payment configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_Tagyut8vJ60g14")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "O9R49p5G387oKaXy5r3VOqY2")
RAZORPAY_CURRENCY = os.getenv("RAZORPAY_CURRENCY", "INR")
USD_TO_INR_RATE = float(os.getenv("USD_TO_INR_RATE", "85.0"))

# Redis Cache configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.7"))

def get_db_connection():
    try:
        import pymysql
        import pymysql.cursors
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        logger.info("MySQL database connected")
        return conn
    except Exception as e:
        logger.error({"error": str(e), "message": "MySQL connection failed"})
        raise