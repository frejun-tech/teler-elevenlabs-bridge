import os

from pydantic_settings import BaseSettings
from app.utils.ngrok_utils import get_server_domain


class Settings(BaseSettings):
    """Application settings"""
    
    # ELEVENLABS Configuration
    elevenlabs_websocket_url: str = os.getenv("ELEVENLABS_WEBSOCKET_URL", "")
    elevenlabs_sample_rate: str = str(os.getenv("ELEVENLABS_SAMPLE_RATE", "16k"))
    
    # Server Configuration - dynamically get ngrok URL
    @property
    def server_domain(self) -> str:
        return get_server_domain()
    
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))
    
    # Teler Configuration
    teler_api_key: str = os.getenv("TELER_API_KEY", "")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()
