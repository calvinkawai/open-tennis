# Project Summary: Tennis Intelligence & Training Journal

---

## 🎾 Project Vision
The **Tennis Intelligence & Training Journal** is a high-performance application designed to provide amateur and competitive tennis players with elite-level technical guidance. By leveraging a **Retrieval-Augmented Generation (RAG)** architecture, the app ensures that training advice is strictly anchored in a proprietary "Source of Truth" maintained by the app owner, while allowing for a highly personalized and mutable user experience.

## ✨ Core Functionality
*   **Intelligent Plan Generation**: Users describe their current technical struggles (e.g., "trouble with serve toss height") in natural language. The system retrieves specific technical documentation and synthesizes a step-by-step training plan.
*   **Technical Source of Truth**: A master database of technical documentation in Markdown format remains immutable to users and the LLM, ensuring the integrity of the coaching methodology.
*   **Mutable Training Plans**: While the technical details are static, the generated plans are fully editable by the user, allowing for adjustments in repetitions, scheduling, and personal notes.
*   **Immutable Journaling**: Users log their progress in a journal that the LLM can read to provide feedback and "Next Steps," but cannot modify, preserving the authenticity of the user's history.
*   **Resource Integration**: Training plans automatically include metadata for video resources, such as YouTube iframes or training links, mapped to specific technical topics.

## 🏗️ Architectural Overview
The system follows a decoupled, **N-Tier architecture** designed for an initial **Web POC** with a roadmap toward a native **iOS application**.

*   **Client Tier**: Next.js (React) for the web interface, utilizing Tailwind CSS for portable UI design.
*   **Orchestration Tier**: A FastAPI backend serves as the central hub, managing API routes, schema validation via Pydantic, and database sessions.
*   **Intelligence Tier (The Brain)**: 
    *   **LangChain**: Orchestrates the flow between the LLM and the Vector Store.
    *   **Google Gemini 1.5 Flash**: Acts as the reasoning engine for synthesis and progress analysis.
*   **Data Tier**: 
    *   **Relational (SQLite/SQLModel)**: Stores user profiles, journal entries, and mutable plans.
    *   **Vector (ChromaDB/FAISS)**: Stores chunked embeddings of the master technical documentation.

## 🛠️ Backend Technical Stack
| Component             | Technology                          |
| :-------------------- | :---------------------------------- |
| **Framework**         | FastAPI                             |
| **ORM**               | SQLModel (SQLAlchemy + Pydantic)   |
| **LLM**               | Google Gemini 1.5 Flash             |
| **Orchestration**     | LangChain                           |
| **Database (Relational)** | SQLite (for POC)                  |
| **Database (Vector)** | ChromaDB / FAISS                    |
| **Migrations**        | Alembic                             |

## 🚀 Roadmap
1.  **Phase 1 (POC)**: Web-based implementation using Next.js and SQLite to validate the RAG logic and user flow.
2.  **Phase 2 (Optimization)**: Transition to PostgreSQL for robust data management and refinement of the `FeedbackService` logic.
3.  **Phase 3 (Mobile)**: Development of a native iOS application, consuming the established FastAPI backend.
