"""LinkedIn Job Poster API - School Project"""

from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import requests
import os
import shutil
import uuid
from dotenv import load_dotenv
from models import JobPostRequest

load_dotenv()

# Get configuration from .env  
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
ME_URL = os.getenv("LINKEDIN_ME_URL")
REGISTER_UPLOAD_URL = os.getenv("LINKEDIN_REGISTER_UPLOAD_URL")
UGC_POSTS_URL = os.getenv("LINKEDIN_UGC_POSTS_URL")

if not ACCESS_TOKEN:
    raise ValueError("Please add LINKEDIN_ACCESS_TOKEN to .env file")
if not all([ME_URL, REGISTER_UPLOAD_URL, UGC_POSTS_URL]):
    raise ValueError("Please add all LinkedIn API URLs to .env file")

app = FastAPI(title="LinkedIn Job Poster")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = Path("temp_uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)


def get_profile_id():
    """Get LinkedIn profile ID"""
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    
    # Try userinfo endpoint first (works with OpenID Connect)
    userinfo_url = "https://api.linkedin.com/v2/userinfo"
    resp = requests.get(userinfo_url, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        # Extract person ID from sub field
        sub = data.get("sub")
        if sub and ":" in sub:
            return sub.split(":")[-1]  # Extract ID from urn:li:person:ID
        return sub
    
    # Fallback to /me endpoint
    resp = requests.get(ME_URL, headers=headers)
    if resp.status_code == 200:
        return resp.json()["id"]
    
    raise ValueError(
        f"Failed to get profile: {resp.status_code} - {resp.text}\n\n"
        "Please ensure your access token has these scopes:\n"
        "- openid (for profile access)\n"
        "- profile (for basic profile)\n"
        "- w_member_social (for posting)\n\n"
        "Get a new token at: https://www.linkedin.com/developers/tools/oauth/token-generator"
    )


def register_image_upload(owner_urn):
    """Register image upload"""
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": owner_urn,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    resp = requests.post(REGISTER_UPLOAD_URL, headers=headers, json=data)
    if resp.status_code != 200:
        raise ValueError(f"Upload registration failed: {resp.text}")
    
    value = resp.json()["value"]
    return value["asset"], value["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]


def upload_image(upload_url, image_path, content_type):
    """Upload image to LinkedIn"""
    with open(image_path, "rb") as f:
        resp = requests.put(upload_url, data=f, headers={"Content-Type": content_type})
    if resp.status_code not in (200, 201, 202):
        raise ValueError(f"Image upload failed: {resp.status_code}")


def create_post(author_urn, text, asset_urn=None):
    """Create LinkedIn post"""
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    post_data = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    
    if asset_urn:
        post_data["specificContent"] = {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{
                    "status": "READY",
                    "description": {"text": "Job posting"},
                    "media": asset_urn,
                    "title": {"text": "We're hiring!"}
                }]
            }
        }
    else:
        post_data["specificContent"] = {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        }
    
    resp = requests.post(UGC_POSTS_URL, headers=headers, json=post_data)
    if resp.status_code not in (201, 202):
        raise ValueError(f"Post creation failed: {resp.text}")
    return resp.json()


@app.get("/")
async def root():
    return {"message": "LinkedIn Job Poster API", "status": "running"}


@app.post("/post-job")
async def post_job(
    job_text: str = Form(...),
    form_link: str = Form(...),
    image: Optional[UploadFile] = File(None)
):
    """Post a job to LinkedIn"""
    
    # Validate input
    try:
        JobPostRequest(job_text=job_text, form_link=form_link)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    temp_file = None
    try:
        # Save image if provided
        if image:
            if image.content_type not in ("image/jpeg", "image/jpg", "image/png"):
                raise HTTPException(400, "Image must be JPG or PNG")
            
            temp_file = UPLOAD_FOLDER / f"{uuid.uuid4().hex}{Path(image.filename).suffix}"
            with temp_file.open("wb") as f:
                shutil.copyfileobj(image.file, f)
        
        # Get profile and create post
        profile_id = get_profile_id()
        owner_urn = f"urn:li:person:{profile_id}"
        full_text = f"{job_text}\n\n📝 Apply here: {form_link}"
        
        asset_urn = None
        if temp_file:
            asset_urn, upload_url = register_image_upload(owner_urn)
            upload_image(upload_url, str(temp_file), image.content_type)
        
        response = create_post(owner_urn, full_text, asset_urn)
        
        return {
            "success": True,
            "message": "Job posted to LinkedIn",
            "linkedin_response": response
        }
    
    except Exception as e:
        raise HTTPException(400, str(e))
    
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)