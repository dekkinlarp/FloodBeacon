from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    twilio_account_sid: str = ''
    twilio_auth_token: str = ''
    twilio_phone_number: str = ''
    twilio_webhook_url: str = ''
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3.5-flash'
    gemini_timeout_seconds: int = Field(default=90, ge=5, le=300)
    operator_api_key: str = ''
    database_path: str = 'data/intake.sqlite3'
    sms_dry_run: bool = True
    session_hours: int = 6
