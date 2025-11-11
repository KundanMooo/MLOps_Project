from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Annotated
import re

class UserData(BaseModel):
    """
    User data validation model for resume upload
    
    This model validates:
    - Name: 2-100 characters, letters only
    - Email: Valid email format
    - Phone: 10-digit Indian mobile number starting with 6, 7, 8, or 9
    """
    
    name: Annotated[
        str,
        Field(
            min_length=2,
            max_length=100,
            description="Full name of the user",
            examples=["John Doe", "Priya Sharma", "Rahul Kumar"]
        )
    ]
    
    email: Annotated[
        EmailStr,
        Field(
            description="Valid email address",
            examples=["john.doe@example.com", "priya.sharma@gmail.com"]
        )
    ]
    
    phone: Annotated[
        int,
        Field(
            ge=6000000000,
            le=9999999999,
            description="10-digit Indian mobile number",
            examples=[9876543210, 8765432109, 7654321098]
        )
    ]
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """
        Validate name format
        - Strips whitespace
        - Allows only letters, spaces, hyphens, apostrophes, and periods
        - Converts to title case
        """
        v = v.strip()
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", v):
            raise ValueError(
                "Name can only contain letters, spaces, hyphens, apostrophes, and periods"
            )
        return v.title()
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: int) -> int:
        """
        Validate Indian mobile number
        - Must be exactly 10 digits
        - Must start with 6, 7, 8, or 9
        """
        phone_str = str(v)
        
        if len(phone_str) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        
        if phone_str[0] not in ['6', '7', '8', '9']:
            raise ValueError("Phone number must start with 6, 7, 8, or 9")
        
        return v
    
    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "name": "Narendar Modi",
                "email": "narendar.modi@gov.in",
                "phone": 9420420420
            }
        }


class ResumeUploadResponse(BaseModel):
    """
    Response model for successful resume upload
    """
    
    success: Annotated[
        bool,
        Field(description="Whether the upload was successful")
    ]
    
    message: Annotated[
        str,
        Field(description="Success or error message")
    ]
    
    data: Annotated[
        dict,
        Field(description="Uploaded resume data details")
    ]
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Resume uploaded successfully",
                "data": {
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "phone": 9876543210,
                    "filename": "20241102_120000_resume.pdf",
                    "text_length": 1250
                }
            }
        }


class ErrorResponse(BaseModel):
    """
    Response model for errors
    """
    
    detail: Annotated[
        str,
        Field(description="Error message describing what went wrong")
    ]
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Validation error: Name can only contain letters"
            }
        }