from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from app.core.config import BACKEND_DIR
from app.core.errors import AppError


def initialize_database(engine: Engine) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if tables and "alembic_version" not in tables:
            expected = {
                "trainingplan": {
                    "id", "title", "focus_area", "raw_ai_content", "edited_content",
                    "created_at", "updated_at",
                },
                "drill": {"id", "name", "description", "video_url", "training_plan_id"},
            }
            if tables != set(expected) or any(
                {item["name"] for item in inspect(connection).get_columns(name)} != columns
                for name, columns in expected.items()
            ):
                raise AppError(
                    "UNKNOWN_DATABASE_SCHEMA",
                    "The unversioned database is not the known legacy schema; back it up and migrate it explicitly.",
                    503,
                )
            command.stamp(config, "6828c22a1516")
        command.upgrade(config, "head")
