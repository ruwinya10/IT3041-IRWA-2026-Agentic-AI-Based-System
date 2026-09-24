from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "AI Study & Research Assistant"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    mysql_url: str
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"
    openalex_email: str = ""
    frontend_url: str = "http://localhost:5173"
    coordinator_agent_url: str = "http://localhost:8004"
    research_agent_url: str = "http://localhost:8001"
    study_agent_url: str = "http://localhost:8002"
    verification_agent_url: str = "http://localhost:8003"
    chroma_path: str = "./chroma_data"
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
