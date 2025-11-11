from langgraph.graph import StateGraph,START,END
from typing import TypedDict,Annotated,Literal
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from dotenv import load_dotenv
from pydantic import BaseModel, Field,field_validator
import operator
import os
from langchain_core.messages import HumanMessage,SystemMessage
import time
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langsmith import traceable
from datetime import datetime
from langchain_core.tools import tool
import smtplib
from email.mime.text import MIMEText
import requests
from src.linkdin.linked_post import linked_post_fun
from src.kundan.supabase_get.app import main
from fastapi import FastAPI
from src.email_send.email_invite import send_interview_invites
import re

from src.backend_jd import workflow

app = FastAPI()


class WorkflowInput(BaseModel):
    topic: str
    iteration: int = 0
    max_iteration: int = 5
    retry_cv: int = 0
    max_retry_cv: int = 3
    min_no_cv_you_want: int = 1
    interview_date: str = "2025-11-11"        # ✅ quotes fixed
    interview_time: str = "10:00"             # ✅ quotes fixed
    min_no_days_you_want_to_collect_cv: int = 5   # ✅ type annotation added
    no_of_student_you_want_for_interview: int = 2 # ✅ type annotation added


@app.post("/predict")
def complete_workflow(input_data: WorkflowInput):
    """
    Trigger the job-description workflow with initial parameters.
    You only need to pass the required fields; defaults handle the rest.
    """
    # Convert Pydantic model to dict
    initial_state = input_data.dict()

    # Call your LangGraph workflow
    result = workflow.invoke(initial_state)
# Extract only required fields safely
    topic = result["topic"]
    selected_students = result["selected_student_for_interview"]

    # Return only what you want to show
    return {
        "topic": topic,
        "selected_students": selected_students
    }






# ---------------- ------------------------- app_offer.py ----------------------------------------------
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Dict
from src.email_send.send_offers import send_offers
from langgraph.graph import StateGraph, START, END
from src.backend_jd import offerlaterworkflow

# ---------------- Workflow Definition ----------------
class OfferLetter(BaseModel):
    candidate: List[Dict] = Field(..., description="List of selected candidates [{'name':..., 'email':...}]")
    role: str = Field(..., description="Role offered to the candidate(s)")
    salary: str = Field(..., description="Salary offered to the candidate(s)")




@app.post("/send_offer")
def send_offer_endpoint(data: OfferLetter):
    """
    🚀 Trigger the Offer Letter workflow.
    Expects a JSON input with candidate list, role, and salary.
    """
    result = offerlaterworkflow.invoke(data.dict())
    return {"status": "✅ Offer letters sent successfully", "result": result}
