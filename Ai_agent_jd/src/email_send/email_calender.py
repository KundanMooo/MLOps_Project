# ---------------- email_gen.py ----------------
import os
import smtplib
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
from datetime import datetime, timedelta
import urllib.parse

# Load environment variables
load_dotenv()

# Get SMTP credentials from .env
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")


# ------------------------------------------------
# 🔹 Function: Generate Google Calendar Link
# ------------------------------------------------
def generate_google_calendar_link(candidate_name, interview_date, start_time, duration_minutes=30):
    """
    Generate a Google Calendar event link for the interview slot.
    """
    # Combine date and time
    start_dt = datetime.strptime(f"{interview_date} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    # Format for Google Calendar (YYYYMMDDTHHMMSSZ)
    start_str = start_dt.strftime("%Y%m%dT%H%M%S")
    end_str = end_dt.strftime("%Y%m%dT%H%M%S")

    # Create event details
    event_title = f"Interview with {candidate_name}"
    event_details = "Interview scheduled for candidate selection process."
    location = "Google Meet / Office"

    # Encode parameters
    params = {
        "action": "TEMPLATE",
        "text": event_title,
        "dates": f"{start_str}/{end_str}",
        "details": event_details,
        "location": location,
    }
    return "https://www.google.com/calendar/render?" + urllib.parse.urlencode(params)


# ------------------------------------------------
# 🔹 Function: Generate email content using LLM
# ------------------------------------------------
def generate_email_with_llm(email_llm, job_description: str, candidate_name: str, interview_date: str, interview_time: str, calendar_link: str):
    """
    Use the structured LLM to generate a personalized interview email
    that includes the calendar link.
    """
    prompt = f"""
    Generate a short, polite, and professional interview invitation email
    for the candidate named {candidate_name}. The interview is scheduled on
    {interview_date} at {interview_time}. Include the following calendar link
    in the email for them to confirm or add the meeting:

    {calendar_link}

    Use the job description below to customize the content.

    Job Description:
    {job_description}
    """

    result = email_llm.invoke(prompt)
    return result.mail_generated


# ------------------------------------------------
# 🔹 Function: Send email via SMTP
# ------------------------------------------------
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


# ------------------------------------------------
# 🔹 Function: Send interview invites
# ------------------------------------------------
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
      2. Generate Google Calendar link (30-min slot)
      3. Send via Gmail SMTP
    """

    if not SMTP_USER or not SMTP_PASS:
        raise ValueError("❌ Missing SMTP credentials in .env file")

    # Parse interview_time (e.g., "14:30")
    current_time = datetime.strptime(interview_time, "%H:%M")

    for candidate in candidate_list:
        name = candidate["name"]
        email = candidate["email"]

        # Format current interview time nicely (e.g. "02:30 PM")
        formatted_time = current_time.strftime("%I:%M %p")

        # Create Google Calendar link
        calendar_link = generate_google_calendar_link(
            candidate_name=name,
            interview_date=interview_date,
            start_time=current_time.strftime("%H:%M"),
        )

        print(f"🧠 Generating personalized email for {name} at {formatted_time}...")

        # Generate personalized email
        email_body = generate_email_with_llm(
            email_llm,
            job_description,
            name,
            interview_date,
            formatted_time,
            calendar_link
        )

        # Send email
        subject = f"Interview Invitation - {name}"
        send_email(email, subject, email_body)

        # Add 30 minutes gap for next candidate
        current_time += timedelta(minutes=30)

    return "✅ All interview invitation emails sent successfully"
