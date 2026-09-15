from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    jwt_secret_key: str = ""
    environment: str = "development"
    payment_gateway_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    ai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    replicate_api_token: str = ""
    tryon_replicate_model: str = "prunaai/p-image-try-on"
    firebase_credentials_json: str = ""

    model_config = SettingsConfigDict(
        env_file=find_dotenv(usecwd=True),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
