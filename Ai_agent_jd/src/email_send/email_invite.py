# ---------------- email_gen.py ----------------
import os
import smtplib
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Get SMTP credentials from .env
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")


def generate_email_with_llm(email_llm, job_description: str, candidate_name: str, interview_date: str, interview_time: str):
    """
    Use the structured LLM to generate a personalized interview email.
    """
    prompt = f"""
    Generate a short, polite, and professional interview invitation email
    for the candidate named {candidate_name}. The interview is scheduled on
    {interview_date} at {interview_time}.
    Use the job description below to customize the content.

    Job Description:
    {job_description}
    """

    result = email_llm.invoke(prompt)
    return result.mail_generated


def send_email(to_email: str, subject: str, body: str):
    """
    Send an email using Gmail SMTP.
    """
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

    print(f"✅ Email sent successfully to {to_email}")


def send_interview_invites(
    candidate_list: List[Dict],
    job_description: str,
    email_llm,
    interview_date: str,
    interview_time: str
):
    """
    For each candidate:
      1. Generate personalized email using LLM
      2. Schedule time slots with 30-min gaps
      3. Send via Gmail SMTP (credentials from .env)
    """

    if not SMTP_USER or not SMTP_PASS:
        raise ValueError("❌ Missing SMTP credentials in .env file")

    # Parse the interview_time string into a datetime object
    # Example expected input: "10:00" (24-hour format)
    current_time = datetime.strptime(interview_time, "%H:%M")

    for candidate in candidate_list:
        name = candidate["name"]
        email = candidate["email"]

        # Format current interview time nicely (e.g. 10:00 AM)
        formatted_time = current_time.strftime("%I:%M %p")

        print(f"🧠 Generating personalized email for {name} at {formatted_time}...")

        email_body = generate_email_with_llm(
            email_llm, job_description, name, interview_date, formatted_time
        )

        subject = f"Interview Invitation - {name}"
        send_email(email, subject, email_body)

        # Add 30 minutes for next candidate
        current_time += timedelta(minutes=30)

    return "✅ All interview invitation emails sent successfully"
