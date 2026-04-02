from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppSettings:
	environment: str = os.getenv("APP_ENVIRONMENT", "development")
	log_level: str = os.getenv("APP_LOG_LEVEL", "DEBUG")


app = AppSettings()
