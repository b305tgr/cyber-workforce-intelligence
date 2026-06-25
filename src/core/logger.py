import logging

from src.core.paths import LOG_DIR


LOG_DIR.mkdir(
    exist_ok=True,
)

LOG_FILE = LOG_DIR / "application.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("cyber_workforce")