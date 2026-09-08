from pathlib import Path
import logging, os

os.makedirs(Path(__file__).parent.parent / "logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            filename=Path(__file__).parent.parent / "logs" / "foodbot.log",
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

def get_logger(name):
    return logging.getLogger(name)