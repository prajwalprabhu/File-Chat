import os
import shutil
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from langchain_huggingface import HuggingFaceEmbeddings
from loguru import logger
from sqlalchemy.orm import Session
from langchain_community.vectorstores import FAISS

from config import EMBEDDINGS_DIR, EMBEDDINGS_MODEL, UPLOAD_DIR
from cookies import get_current_user
from models import File, get_db
from utils import process_file

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/upload")


# File Upload and Management
@router.get("/", response_class=HTMLResponse)
def upload_page(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int | None = Depends(get_current_user),
):
    if not user_id:
        return HTMLResponse("<div class='alert alert-danger'>Please log in!</div>")
    files = db.query(File).filter(File.user_id == user_id).all()
    return templates.TemplateResponse(
        "upload.html", {"request": request, "title": "Upload File", "files": files}
    )


@router.post("/", response_class=HTMLResponse)
def upload_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    user_id: int | None = Depends(get_current_user),
    request: Request = None,
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    # Create user-specific directory
    user_upload_dir = os.path.join(UPLOAD_DIR, str(user_id))
    os.makedirs(user_upload_dir, exist_ok=True)

    # Save file in user's directory
    file_path = os.path.join(user_upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create user-specific embeddings directory
    user_embeddings_dir = os.path.join(EMBEDDINGS_DIR, str(user_id))
    os.makedirs(user_embeddings_dir, exist_ok=True)
    print(user_embeddings_dir, user_upload_dir)
    embeddings_path = process_file(
        file_path,
        user_id=user_id,
        file_name=file.filename,
        embeddings_dir=EMBEDDINGS_DIR,
    )

    uploaded_file = File(
        user_id=user_id,
        filename=file.filename,
        file_path=file_path,
        embeddings_path=embeddings_path,
    )
    db.add(uploaded_file)
    db.commit()
    return templates.TemplateResponse(
        "partials/file_row.html",
        {"request": request, "file": uploaded_file},
        headers={"Content-Type": "text/html"},
    ).body


@router.delete("/", response_class=HTMLResponse)
def delete_file(
    file_id: int = Form(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    embeddings_model = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
    file = db.query(File).filter(File.id == file_id, File.user_id == user_id).first()
    if not file:
        return ""

    # Delete physical file

    # Load and update FAISS index
    embeddings_path = str(file.embeddings_path)

    if os.path.exists(embeddings_path):
        print(f"Loading embeddings from {embeddings_path}")
        vectorstore = FAISS.load_local(
            embeddings_path, embeddings_model, allow_dangerous_deserialization=True
        )
        # Filter out embeddings for this file
        filtered_docs = [
            doc
            for doc in vectorstore.docstore._dict.values()
            if doc.metadata.get("file_name") != file.filename
        ]
        logger.info(
            "Files {} ",
            set(
                [
                    doc.metadata.get("file_name")
                    for doc in vectorstore.docstore._dict.values()
                ]
            ),
        )
        logger.info(
            "Filtered Files : {}",
            set([doc.metadata.get("file_name") for doc in filtered_docs]),
        )
        # filtered_docs = filtered_docs if len(filtered_docs) > 0 else ["dummy"]
        if len(filtered_docs) > 0:
            new_vectorstore = FAISS.from_documents(filtered_docs, embeddings_model)
            new_vectorstore.save_local(embeddings_path)
        else:
            new_vectorstore = FAISS.from_texts(["dummy"], embeddings_model)
            new_vectorstore.save_local(embeddings_path)
    if os.path.exists(file.file_path):
        os.remove(file.file_path)
    db.delete(file)
    db.commit()

    return ""
