from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import os
import re
import PyPDF2
from io import BytesIO
from models import UserData, ResumeUploadResponse, ErrorResponse

load_dotenv()

app = FastAPI(
    title="Resume Upload API",
    description="API for uploading resumes with validation",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from PDF"""
    try:
        pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except:
        return ""

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Resume Upload API", "status": "running"}

@app.post(
    "/upload-resume",
    response_model=ResumeUploadResponse,
    responses={
        200: {"model": ResumeUploadResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def upload_resume(
    name: str = Form(..., description="Full name"),
    email: str = Form(..., description="Email address"),
    phone: int = Form(..., description="10-digit mobile number"),
    file: UploadFile = File(..., description="Resume PDF file")
):
    """
    Upload resume with user details
    
    - **name**: Full name (2-100 characters, letters only)
    - **email**: Valid email address
    - **phone**: 10-digit Indian mobile number (starts with 6/7/8/9)
    - **file**: PDF resume (max 10MB)
    """
    try:
        # Validate data
        user_data = UserData(name=name, email=email, phone=phone)
        
        # Validate file
        if not file.filename.endswith('.pdf'):
            raise HTTPException(400, "Only PDF files allowed")
        
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(400, "File too large (max 10MB)")
        
        # Extract text
        pdf_text = extract_pdf_text(file_bytes)
        
        # Upload to storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
        filename = f"{timestamp}_{safe_filename}"
        file_path = f"allpdfs/{filename}"
        
        supabase.storage.from_("Pdfs_").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )
        
        # Save to database
        db_data = {
            "Name": user_data.name,
            "Email_id": user_data.email.lower(),
            "Mobile_No.": str(user_data.phone),
            "Resume": file_path,
            "Resume_Text": pdf_text
        }
        
        supabase.table("Data_Storage").insert(db_data).execute()
        
        return {
            "success": True,
            "message": "Resume uploaded successfully",
            "data": {
                "name": user_data.name,
                "email": user_data.email,
                "phone": user_data.phone,
                "filename": filename,
                "text_length": len(pdf_text)
            }
        }
        
    except ValueError as e:
        raise HTTPException(400, f"Validation error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        supabase.table("Data_Storage").select("id").limit(1).execute()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}