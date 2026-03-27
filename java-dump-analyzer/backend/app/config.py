from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_db: str = "dumpanalyzer"
    postgres_user: str = "admin"
    postgres_password: str = "changeme"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "dumps"

    secret_key: str = "changeme-secret-key"
    max_upload_size_mb: int = 4096
    input_dumps_dir: str = "/data/dumps"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
