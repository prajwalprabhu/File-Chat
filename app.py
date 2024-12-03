from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeSerializer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session
from config import EMBEDDINGS_DIR, GROQ_API_KEY, SECRET_KEY, UPLOAD_DIR
from cookies import SecureCookieManager, get_current_user
from middlewares import AuthenticatedStaticFiles
from models import Chat, ChatMessage, User, File, get_db
import os
import shutil
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain

# import huggingface embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document

from sentence_transformers import SentenceTransformer
from fastapi import Cookie, HTTPException, status


from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from utils import process_file, render_markdown_safely

# Load environment variables
load_dotenv()


app = FastAPI()

# Add SessionMiddleware with a secret key
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,  # Use a strong secret key in production
)

# Optional: Add CORS middleware if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Jinja2 templates
templates = Jinja2Templates(directory="templates")

from typing import Optional
from fastapi import HTTPException

# You'll need to create your User model


# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", AuthenticatedStaticFiles(directory=UPLOAD_DIR), name="uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
from langchain_groq import ChatGroq

# Initialize ChatGroq and free embeddings model

# Free embeddings model


# ------------- Routes ----------------

from routes.user import router as userRouter
from routes.upload import router as uploadRouter
from routes.chat import router as chatRouter


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return RedirectResponse(url="/chat")


app.include_router(userRouter)
app.include_router(uploadRouter)
app.include_router(chatRouter)


from fastapi.responses import JSONResponse, Response
from typing import Literal
import pandas as pd
from io import StringIO


@app.get("/export/chat")
def export_chat(
    type: Literal["json", "csv"],
    request: Request,
    user_id: int = Depends(get_current_user),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    chat_history = request.session.get("chat_history", [])

    if type == "json":
        return JSONResponse(
            content=chat_history,
            headers={"Content-Disposition": "attachment; filename=chat_export.json"},
        )

    elif type == "csv":

        df = pd.DataFrame(chat_history)
        output = StringIO()
        response = Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=chat_export.csv"},
        )
        output.close()
        return response

    raise HTTPException(status_code=400, detail="Invalid export type")
