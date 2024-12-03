#!/bin/zsh

# Define project structure
declare -A module_files=(
  ["app/__init__.py"]=""
  ["app/main.py"]="""from fastapi import FastAPI
from app.routes import chat_routes, file_routes, user_routes
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(user_routes.router)
app.include_router(file_routes.router)
app.include_router(chat_routes.router)

app.mount('/static', StaticFiles(directory='static'), name='static')
"""
  ["app/auth/__init__.py"]=""
  ["app/auth/secure_cookie.py"]="""from itsdangerous import URLSafeSerializer
from datetime import datetime, timedelta

class SecureCookieManager:
    def __init__(self, secret_key: str):
        self.serializer = URLSafeSerializer(secret_key, salt='cookie-salt')

    def create_secure_cookie(self, user_id: int, expires_in: timedelta = timedelta(days=7)):
        payload = {
            'user_id': user_id,
            'expires': (datetime.utcnow() + expires_in).timestamp(),
        }
        return self.serializer.dumps(payload)

    def decode_secure_cookie(self, cookie_value: str):
        try:
            payload = self.serializer.loads(cookie_value)
            if datetime.fromtimestamp(payload['expires']) < datetime.utcnow():
                return None
            return payload['user_id']
        except:
            return None
"""
  ["app/auth/authentication.py"]="""from fastapi import Depends, HTTPException, Cookie
from app.models.user import User
from app.models.database import get_db

async def get_current_user(user_id: str = Cookie(default=None), db=Depends(get_db)):
    from app.auth.secure_cookie import SecureCookieManager
    from dotenv import load_dotenv
    import os

    load_dotenv()
    SECRET_KEY = os.getenv('SECRET_KEY')
    cookie_manager = SecureCookieManager(SECRET_KEY)
    decoded_user_id = cookie_manager.decode_secure_cookie(user_id)

    if not decoded_user_id:
        raise HTTPException(status_code=401, detail='Authentication required')

    user = db.query(User).filter(User.id == decoded_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user
"""
  ["app/routes/__init__.py"]=""
  ["app/routes/chat_routes.py"]="""from fastapi import APIRouter, Request
from app.utils.vectorstore_handler import retrieve_answer

router = APIRouter()

@router.get('/chat')
async def chat_page(request: Request):
    return {'message': 'Chat Page'}

@router.post('/chat')
async def chat(request: Request, query: str):
    response = retrieve_answer(query)
    return {'response': response}
"""
  ["app/routes/file_routes.py"]="""from fastapi import APIRouter, UploadFile, Depends, HTTPException
from app.models.file import File
from app.utils.vectorstore_handler import process_file
import os
import shutil

router = APIRouter()

@router.post('/upload-file')
async def upload_file(file: UploadFile, user_id: int = Depends()):
    user_upload_dir = os.path.join('uploads', str(user_id))
    os.makedirs(user_upload_dir, exist_ok=True)

    file_path = os.path.join(user_upload_dir, file.filename)
    with open(file_path, 'wb') as buffer:
        shutil.copyfileobj(file.file, buffer)

    embeddings_path = process_file(file_path, user_id)
    return {'message': 'File processed successfully', 'embeddings_path': embeddings_path}
"""
  ["app/routes/user_routes.py"]="""from fastapi import APIRouter

router = APIRouter()

@router.get('/signup')
async def signup_page():
    return {'message': 'Signup Page'}

@router.get('/login')
async def login_page():
    return {'message': 'Login Page'}
"""
  ["app/models/__init__.py"]=""
  ["app/models/user.py"]="""from sqlalchemy import Column, Integer, String
from app.models.database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
"""
  ["app/models/file.py"]="""from sqlalchemy import Column, Integer, String
from app.models.database import Base

class File(Base):
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    filename = Column(String)
    file_path = Column(String)
    embeddings_path = Column(String)
"""
  ["app/models/database.py"]="""from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""
  ["app/utils/__init__.py"]=""
  ["app/utils/text_processing.py"]="""# Add text processing utilities here
"""
  ["app/utils/vectorstore_handler.py"]="""from langchain_community.vectorstores import FAISS

def process_file(file_path: str, user_id: int):
    # Logic to process files and generate embeddings
    return 'Embeddings Path'

def retrieve_answer(query: str):
    # Logic to retrieve answer from vector store
    return 'Answer'
"""
)

# Create directories and files with content
for file in ${(k)module_files}; do
  mkdir -p $(dirname $file)
  echo "${module_files[$file]}" > $file
done

