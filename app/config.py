import os
from functools import lru_cache
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

class Settings(BaseModel):
    # Server
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    app_base_url: str = Field(default_factory=lambda: os.getenv("APP_BASE_URL", "http://localhost:8000"))

    # Gemini AI
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.6-flash"))

    # PayPal
    paypal_client_id: str = Field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_ID", ""))
    paypal_client_secret: str = Field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_SECRET", ""))
    paypal_mode: str = Field(default_factory=lambda: os.getenv("PAYPAL_MODE", "sandbox").lower())
    paypal_webhook_id: str = Field(default_factory=lambda: os.getenv("PAYPAL_WEBHOOK_ID", ""))

    # Database
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./splitpay.db"))

    @property
    def paypal_api_base(self) -> str:
        if self.paypal_mode == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    @property
    def is_paypal_configured(self) -> bool:
        if not (self.paypal_client_id and self.paypal_client_secret):
            return False
        if "your_" in self.paypal_client_id.lower() or "your_" in self.paypal_client_secret.lower():
            return False
        return True

    @property
    def is_gemini_configured(self) -> bool:
        if not self.gemini_api_key:
            return False
        if "your_" in self.gemini_api_key.lower():
            return False
        return True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
