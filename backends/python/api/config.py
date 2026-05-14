from dataclasses import dataclass
from environs import Env

env = Env()


@dataclass
class Config:
    # Django
    debug: bool

    # Database
    db_type: str
    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int

    # Cloudpub
    cloudpub_token: str

    # JWT
    jwt_secret: str
    jwt_algorithm: str

    # B24 Application
    client_id: str
    client_secret: str

    # VIRTUAL_HOST
    app_base_url: str

    # OpenTelemetry (optional)
    otel_enabled: bool
    otel_endpoint: str
    otel_service_name: str


def load_config() -> Config:
    build_target = env.str("BUILD_TARGET", "dev")  # dev or production
    debug = build_target.lower() == "dev"
    db_type = env.str("DB_TYPE", "postgresql").lower()
    default_db_port = 3306 if db_type == "mysql" else 5432
    otel_endpoint = env.str("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    return Config(
        debug=debug,
        db_type=db_type,
        db_name=env.str("DB_NAME", "appdb"),
        db_user=env.str("DB_USER", "appuser"),
        db_password=env.str("DB_PASSWORD", "apppass"),
        db_host=env.str("DB_HOST", "database"),
        db_port=env.int("DB_PORT", default_db_port),
        cloudpub_token=env.str("CLOUDPUB_TOKEN", ""),
        jwt_secret=env.str("JWT_SECRET", "default_jwt_secret"),
        jwt_algorithm=env.str("JWT_ALGORITHM", "HS256"),
        client_id=env.str("CLIENT_ID", "client_id"),
        client_secret=env.str("CLIENT_SECRET", "client_secret"),
        app_base_url=env.str("VIRTUAL_HOST", "app_base_url"),
        otel_enabled=env.bool("OTEL_EXPORTER_OTLP_ENABLED", (not debug) and bool(otel_endpoint)),
        otel_endpoint=otel_endpoint,
        otel_service_name=env.str("OTEL_SERVICE_NAME", "excel-migration-api"),
    )


config = load_config()
