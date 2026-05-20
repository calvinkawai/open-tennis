from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()


def store_intact_markdown(docs_path: str, database_path: str):
    # 1. Load the markdown files completely intact
    loader = DirectoryLoader(docs_path, glob="**/*.md", loader_cls=TextLoader)
    raw_documents = loader.load()

    # 2. Define the Gemini embedding function
    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")

    # 3. Initialize an empty Chroma database collection first
    vector_db = Chroma(embedding_function=embeddings, persist_directory=database_path)

    # 4. Feed documents individually to bypass the upstream batch-flattening bug
    indexed_count = 0
    for doc in raw_documents:
        # Guard clause against zero-byte or completely blank markdown files
        if doc.page_content.strip():
            vector_db.add_documents([doc])
            indexed_count += 1

    print(f"Successfully indexed {indexed_count} whole file(s) into ChromaDB.")
    return vector_db


store_intact_markdown("data/tutorial", "data/chroma_db")
