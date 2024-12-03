from datetime import datetime
import os
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    CSVLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


from langchain_community.vectorstores import FAISS


def get_loader_for_file(file_path: str):
    file_extension = file_path.split(".")[-1].lower()

    loaders = {
        "txt": TextLoader,
        "pdf": PyPDFLoader,
        "csv": CSVLoader,
        "docx": Docx2txtLoader,
        "xlsx": UnstructuredExcelLoader,
        "xls": UnstructuredExcelLoader,
        "md": UnstructuredMarkdownLoader,
    }

    return loaders.get(file_extension)


def process_file(file_path: str, user_id: int, file_name: str, embeddings_dir: str):
    embeddings_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    """Processes multiple file types, generates embeddings with metadata, and stores them."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )

    # Get appropriate loader
    LoaderClass = get_loader_for_file(file_path)
    if not LoaderClass:
        raise ValueError(f"Unsupported file type: {file_path}")

    loader = LoaderClass(file_path)
    raw_documents = loader.load()
    documents = text_splitter.split_documents(raw_documents)

    for i, doc in enumerate(documents):
        doc.metadata = {
            "user_id": user_id,
            "file_name": file_name,
            "chunk_id": i,
            "source": file_path,
            "created_at": datetime.now().isoformat(),
        }

    user_embeddings_dir = os.path.join(embeddings_dir, str(user_id))
    os.makedirs(user_embeddings_dir, exist_ok=True)

    embeddings_path = os.path.join(user_embeddings_dir, "vectorstore.faiss")
    if os.path.exists(embeddings_path):
        vectorstore = FAISS.load_local(
            embeddings_path, embeddings_model, allow_dangerous_deserialization=True
        )
        vectorstore.add_documents(documents)

    else:
        vectorstore = FAISS.from_documents(documents, embeddings_model)

    vectorstore.save_local(embeddings_path)
    return embeddings_path


from markdown import markdown
import bleach


def render_markdown_safely(content: str) -> str:
    # Allow specific HTML tags and attributes
    allowed_tags = [
        "p",
        "br",
        "pre",
        "code",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "em",
        "ul",
        "ol",
        "li",
        "blockquote",
        "a",
        "table",
    ]
    allowed_attributes = {"a": ["href", "title"]}

    # Convert markdown to HTML and sanitize
    html = markdown(content, extensions=["fenced_code", "codehilite"])
    clean_html = bleach.clean(
        html, tags=allowed_tags, attributes=allowed_attributes, strip=True
    )
    return clean_html
