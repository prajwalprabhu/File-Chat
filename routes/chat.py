import os
from typing import Optional
from fastapi import APIRouter, Depends, Form, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from loguru import logger
from sqlalchemy.orm import Session

from config import EMBEDDINGS_DIR, EMBEDDINGS_MODEL, GROQ_API_KEY
from cookies import get_current_user
from models import Chat, ChatMessage, File, get_db
from utils import render_markdown_safely


chat_model = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama3-8b-8192",
)
router = APIRouter(prefix="/chat")
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def chat_page(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int | None = Depends(get_current_user),
):
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    files = db.query(File).filter(File.user_id == user_id).all()
    # Initialize empty chat history in session
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "title": "Chat",
            "files": files,
            "chats": chats,
            "chat_history": [],
            "chat_id": -1,
        },
    )


@router.get("/{chat_id}", response_class=HTMLResponse)
def chat_page_with_chat_id(
    request: Request,
    chat_id: int = Path(...),
    db: Session = Depends(get_db),
    user_id: int | None = Depends(get_current_user),
):

    if not user_id:
        return RedirectResponse("/login", status_code=303)

    chats = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).all()
    return templates.TemplateResponse(
        "message_list.html",
        {
            "request": request,
            "chat_history": [
                {
                    "type": chat.type,
                    "content": chat.content,
                    "source": chat.source_file,
                    "url": f"/uploads/{user_id}/{chat.source_file}",
                }
                for chat in chats
            ],
            "chat_id": chat_id,
        },
    )


@router.delete("/{chat_id}", response_class=HTMLResponse)
def delete_chat(
    chat_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if not chat:
        return ""
    db.delete(chat)
    db.commit()
    return ""


@router.get("/chats")
def chat_list(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int | None = Depends(get_current_user),
):
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "chat_list.html",
        {
            "request": request,
            "title": "Chat",
            "chats": chats,
        },
    )


@router.get("/chats/latest")
def chat_list_latest(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int | None = Depends(get_current_user),
):
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .limit(1)
        .all()
    )
    return templates.TemplateResponse(
        "chat_list.html",
        {
            "request": request,
            "title": "Chat",
            "chats": chats,
        },
    )


from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


@router.post("/", response_class=HTMLResponse)
def new_chat(
    chat_id: int = Form(...),
    query: str = Form(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
    request: Request = None,
):
    embeddings_model = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
    chat = None
    if chat_id != -1:
        chat = (
            db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
        )
    else:
        llm = ChatGroq(model="llama3-8b-8192")
        prompt = ChatPromptTemplate.from_template(
            f""""
            This is the user question : {query}
            based on this generate routerropriate title
            RETURN ONLY TITLE
            """
        )
        llm_chain = prompt | llm | StrOutputParser()
        title = llm_chain.invoke({"query": query}).strip('"').strip("'")
        logger.info("Title: {}", title)
        chat = Chat(user_id=user_id, title=title)
        db.add(chat)
        db.commit()
        db.refresh(chat)
    # get latest 5 chats
    chat_history = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(2)
        .all()
    )

    embeddings_path = os.path.join(EMBEDDINGS_DIR, str(user_id), "vectorstore.faiss")
    vectorstore = FAISS.load_local(
        embeddings_path, embeddings_model, allow_dangerous_deserialization=True
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    from langchain.text_splitter import TokenTextSplitter

    def format_docs(docs):
        text_splitter = TokenTextSplitter(chunk_size=2000, chunk_overlap=0)
        combined_content = "\n\n".join(doc.page_content for doc in docs)
        truncated_content = text_splitter.split_text(combined_content)[0]
        print(truncated_content)
        return truncated_content

    template = """Answer the question based on the following context and chat history:
    Context: {context}
    Chat History: {chat_history}
    Question: {question}
    """

    prompt = ChatPromptTemplate.from_template(template)
    print(chat_history)

    chain = (
        {
            "context": retriever | format_docs,
            "chat_history": lambda _: [
                (
                    HumanMessage(content=f"{message.content}")
                    if message.type == "human"
                    else AIMessage(content=message.content)
                )
                for message in chat_history
            ],
            "question": RunnablePassthrough(),
        }
        | prompt
        | chat_model
        | StrOutputParser()
    )

    result = chain.invoke(query)
    matched_docs = retriever.get_relevant_documents(query)
    matched_file = (
        matched_docs[0].metadata.get("file_name", "Unknown File")
        if matched_docs
        else "Unknown File"
    )

    # Update chat history
    ai_message = {
        "type": "ai",
        "content": render_markdown_safely(result),
        "source": matched_file,
        "url": f"/uploads/{user_id}/{matched_file}",
    }
    db.add(ChatMessage(chat_id=chat.id, content=query, type="human"))
    db.add(
        ChatMessage(
            chat_id=chat.id,
            content=render_markdown_safely(result),
            type="ai",
            source_file=matched_file,
        )
    )
    db.commit()

    return (
        templates.TemplateResponse(
            "partials/message.html",
            {
                "request": request,
                "message": {"type": "human", "content": query},
                "chat_id": chat.id,
            },
        ).body
        + templates.TemplateResponse(
            "partials/message.html",
            {"request": request, "message": ai_message, "chat_id": chat.id},
        ).body
    )
