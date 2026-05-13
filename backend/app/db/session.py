from sqlmodel import Session, create_engine

# Create the sqlite file path
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///data/{sqlite_file_name}"

# connect_args={"check_same_thread": False} is required for SQLite + FastAPI
# because FastAPI can handle requests in multiple threads.
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False}, echo=True)


def get_session():
    """
    FastAPI Dependency: Yields a new session for every request and
    closes it when the request is done.
    """
    with Session(engine) as session:
        yield session
