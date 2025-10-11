#!/usr/bin/env python3
"""
Demo: schedule interview (send .ics via SMTP) + generate & send offer (OpenAI) + persist to SQLite.
Usage:
  - Set env vars (see instructions)
  - Run: python schedule_and_offer.py demo_invite
  - Run: python schedule_and_offer.py demo_offer
"""

import os
import sqlite3
import uuid
import smtplib
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import urllib.parse
import openai
import sys

# ENV VARS (set these before running)
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")      # e.g., smtp.gmail.com or localhost for MailHog
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))      # 587 for Gmail, 1025 for MailHog
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "no-reply@example.com")

# Webhook base URL where the Flask accept endpoint will be reachable
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")

# HMAC secret for signed accept links
HMAC_SECRET = os.getenv("HMAC_SECRET", "replace_with_strong_secret").encode()

# OpenAI key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

DB_PATH = os.getenv("DB_PATH", "resumes.db")


# ----------------- Utilities -----------------
def create_tables():
    """Create interviews and offers tables if not present."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_email TEXT,
            candidate_name TEXT,
            event_uid TEXT,
            scheduled_at TEXT,
            duration_mins INTEGER,
            meeting_link TEXT,
            status TEXT DEFAULT 'scheduled'
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_email TEXT,
            candidate_name TEXT,
            offer_text TEXT,
            offer_sent_at TEXT,
            offer_status TEXT DEFAULT 'sent'
        )
        """)
        conn.commit()
    print("DB tables ready.")


def create_ics(uid, summary, dtstart_utc, dtend_utc, description, location):
    dtstart = dtstart_utc.strftime("%Y%m%dT%H%M%SZ")
    dtend = dtend_utc.strftime("%Y%m%dT%H%M%SZ")
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Company-A//RecruitmentAgent//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
END:VEVENT
END:VCALENDAR
"""
    return ics


def send_email_with_ics(from_addr, to_addr, subject, body, ics_text,
                        smtp_host=SMTP_HOST, smtp_port=SMTP_PORT, smtp_user=SMTP_USER, smtp_pass=SMTP_PASS):
    msg = MIMEMultipart('mixed')
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject

    # plain body
    msg_alt = MIMEMultipart('alternative')
    msg_text = MIMEText(body, "plain")
    msg_alt.attach(msg_text)
    msg.attach(msg_alt)

    # attach ics
    part = MIMEBase('text', 'calendar', method="REQUEST", name="invite.ics")
    part.set_payload(ics_text)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename="invite.ics"')
    part.add_header('Content-Class', 'urn:content-classes:calendarmessage')
    msg.attach(part)

    s = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
    try:
        # if using TLS server like Gmail
        if smtp_port == 587:
            s.starttls()
            if smtp_user and smtp_pass:
                s.login(smtp_user, smtp_pass)
        elif smtp_user and smtp_pass and smtp_port not in (25, 1025):
            # non-standard: try login if credentials provided
            s.starttls()
            s.login(smtp_user, smtp_pass)
        s.sendmail(from_addr, to_addr, msg.as_string())
        print(f"Email (with .ics) sent to {to_addr}")
    finally:
        s.quit()


def sign_token(candidate_email: str, offer_id: int, action: str) -> str:
    """Return a URL-safe HMAC signature token for (email, offer_id, action)."""
    msg = f"{candidate_email}|{offer_id}|{action}".encode()
    sig = hmac.new(HMAC_SECRET, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode()


def verify_token(candidate_email: str, offer_id: int, action: str, token: str) -> bool:
    expected = sign_token(candidate_email, offer_id, action)
    # constant-time compare
    return hmac.compare_digest(expected, token)


# ----------------- Core demo flows -----------------
def schedule_interview_and_send_invite(candidate_email: str, candidate_name: str,
                                       topic: str, start_dt_utc: datetime, duration_mins: int = 30):
    """
    - Creates an interview record in DB
    - Sends an .ics invite to candidate via SMTP
    """
    uid = str(uuid.uuid4())
    end_dt = start_dt_utc + timedelta(minutes=duration_mins)
    summary = f"Interview: {topic} - Company-A"
    description = f"Interview for {topic}. If you need to reschedule, reply to this email."
    location = "Online"

    ics = create_ics(uid, summary, start_dt_utc, end_dt, description, location)

    # save interview record
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO interviews (candidate_email, candidate_name, event_uid, scheduled_at, duration_mins, meeting_link, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (candidate_email, candidate_name, uid, start_dt_utc.isoformat(), duration_mins, location, 'scheduled'))
        conn.commit()
        interview_id = cur.lastrowid

    # send email (demo body; you can use OpenAI to generate better text)
    body = f"Hi {candidate_name},\n\nYou are invited for an interview for the role: {topic}.\nScheduled (UTC): {start_dt_utc.isoformat()} for {duration_mins} minutes.\nPlease find the attached calendar invite.\n\nRegards,\nCompany-A HR"
    try:
        send_email_with_ics(FROM_EMAIL, candidate_email, f"Interview Invitation — {topic}", body, ics)
    except Exception as e:
        print("Failed to send invite:", e)

    print(f"Interview record saved (id={interview_id}, uid={uid})")
    return interview_id, uid


def generate_offer_text(candidate_name: str, role: str, salary_str: str, start_date: str) -> str:
    """Use OpenAI to generate a formal offer letter text. If no OpenAI key, use a simple template."""
    if OPENAI_API_KEY:
        # simple prompt
        prompt = f"""Write a professional offer letter for {candidate_name} for the role of {role}.
Include salary: {salary_str}, start date: {start_date}. Keep it short and formal, include next steps and acceptance instructions."""
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o",  # or gpt-4o-mini if gpt-4o not available
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            content = resp["choices"][0]["message"]["content"]
            return content
        except Exception as e:
            print("OpenAI call failed, falling back to template. Error:", e)

    # fallback template
    return (f"Dear {candidate_name},\n\n"
            f"We are pleased to offer you the position of {role} at Company-A.\n"
            f"Compensation: {salary_str}\n"
            f"Start date: {start_date}\n\n"
            f"Please accept using the link provided in this email.\n\nRegards,\nCompany-A HR")


def send_offer_email(candidate_email: str, candidate_name: str, role: str, salary_str: str, start_date: str):
    """Create offer record (DB), generate offer text (OpenAI), and send email with accept/decline links."""
    # 1) create DB entry
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO offers (candidate_email, candidate_name, offer_text, offer_sent_at, offer_status)
        VALUES (?, ?, ?, ?, ?)
        """, (candidate_email, candidate_name, "", datetime.utcnow().isoformat(), "pending"))
        conn.commit()
        offer_id = cur.lastrowid

    # 2) generate offer text
    offer_text = generate_offer_text(candidate_name, role, salary_str, start_date)

    # 3) update DB with offer_text & sent time
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE offers SET offer_text = ?, offer_sent_at = ?, offer_status = ? WHERE id = ?",
                    (offer_text, datetime.utcnow().isoformat(), "sent", offer_id))
        conn.commit()

    # 4) create accept/decline links (signed)
    accept_token = sign_token(candidate_email, offer_id, "accept")
    decline_token = sign_token(candidate_email, offer_id, "decline")
    accept_qs = urllib.parse.urlencode({"email": candidate_email, "offer_id": offer_id, "action": "accept", "token": accept_token})
    decline_qs = urllib.parse.urlencode({"email": candidate_email, "offer_id": offer_id, "action": "decline", "token": decline_token})
    accept_link = f"{WEBHOOK_BASE}/offer/respond?{accept_qs}"
    decline_link = f"{WEBHOOK_BASE}/offer/respond?{decline_qs}"

    # 5) compose email body with links
    body = (f"Dear {candidate_name},\n\n{offer_text}\n\n"
            f"To accept the offer click here: {accept_link}\n"
            f"To decline the offer click here: {decline_link}\n\n"
            f"Regards,\nCompany-A HR")

    # send email (simple SMTP)
    msg = MIMEText(body)
    msg['Subject'] = f"Offer Letter — {role} (Company-A)"
    msg['From'] = FROM_EMAIL
    msg['To'] = candidate_email

    try:
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if SMTP_PORT == 587 and SMTP_USER and SMTP_PASS:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(FROM_EMAIL, [candidate_email], msg.as_string())
        s.quit()
        print(f"Offer email sent to {candidate_email} (offer_id={offer_id})")
    except Exception as e:
        print("Failed to send offer email:", e)

    return offer_id


# ----------------- Demo commands -----------------
def demo_invite():
    create_tables()
    # Replace these demo values
    candidate_email = "student@example.com"
    candidate_name = "Student A"
    topic = "Data Analyst"
    start_dt = datetime.utcnow() + timedelta(days=1, hours=1)
    schedule_interview_and_send_invite(candidate_email, candidate_name, topic, start_dt, duration_mins=30)


def demo_offer():
    create_tables()
    candidate_email = "student@example.com"
    candidate_name = "Student A"
    role = "Data Analyst"
    salary = "8 LPA"
    start_date = (datetime.utcnow() + timedelta(days=14)).date().isoformat()
    send_offer_email(candidate_email, candidate_name, role, salary, start_date)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python schedule_and_offer.py demo_invite | demo_offer")
    else:
        cmd = sys.argv[1]
        if cmd == "demo_invite":
            demo_invite()
        elif cmd == "demo_offer":
            demo_offer()
        else:
            print("Unknown command:", cmd)
