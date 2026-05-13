# Backend Tech Stack Summary

---

## 1. Core Framework & API Layer
*   **FastAPI**: The primary web framework for building asynchronous, high-performance API endpoints.
*   **Pydantic**: Handles strict data validation for incoming requests (e.g., journal entries) and outgoing responses.
*   **uv**: A high-performance Python package installer and resolver used to manage dependencies and virtual environments.

## 2. Database & Persistence Layer
*   **SQLModel (ORM)**: A library that bridges SQLAlchemy and Pydantic, allowing for a single definition of database tables and validation schemas.
*   **SQLite**: The relational database used for the Proof of Concept (POC) to ensure easy local development and sharing.
*   **Alembic**: The migration management tool used to version control the database schema as the application evolves.

## 3. Intelligence & Search Tier
*   **LangChain**: The orchestration layer that manages prompt templates, retrieval chains, and the logic connecting the LLM to technical data.
*   **Google Gemini (1.5 Flash)**: The reasoning engine responsible for synthesizing technical documentation into plans and providing feedback on progress.
*   **ChromaDB**: The primary vector database used to store and query mathematical embeddings of proprietary tennis technical documentation. It supports efficient semantic search and metadata filtering for manual chunks.

## 4. Infrastructure & Configuration
*   **Pydantic Settings**: Manages environment variables and secrets (like Gemini API keys) with type-safety and validation.
*   **Python-Dotenv**: Loads local `.env` files into the environment for secure configuration management.

---

### Folder Architecture Preview
```text
backend/
├── app/
│   ├── api/          # Routes & Versioning
│   ├── core/         # Config & Security
│   ├── db/           # Session & Engine
│   ├── models/       # SQLModel definitions
│   ├── services/     # Logic (LLM, Vector, Feedback)
│   └── crud/         # DB operations
├── data/
│   ├── tennis_app.db # Relational SQLite storage
│   └── chroma/       # ChromaDB vector index & metadata
└── alembic/          # Migration scripts
```

### DB Migration

```bash
alembic revision --autogenerate -m "{message}"
alembic upgrade head
```
