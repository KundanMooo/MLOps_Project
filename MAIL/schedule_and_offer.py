"""
Simplified demo: schedule interview (send .ics via SMTP) + generate & send offer (OpenAI optional) + persist to SQLite.

Usage:
  - Create a .env (example provided)
  - Install python-dotenv if not installed: uv add python-dotenv
  - Run: python schedule_and_offer.py demo_invite
  - Run: python schedule_and_offer.py demo_offer
"""

import os
from dotenv import load_dotenv
load_dotenv()

import sqlite3
import uuid
import smtplib
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import urllib.parse
import openai
import sys

# ENV VARS (set in .env)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "no-reply@example.com")

# OpenAI key (optional)
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
            role TEXT,
            salary TEXT,
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
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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

    # connect and send
    s = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
    try:
        # Gmail and most providers use STARTTLS on 587
        if smtp_port == 587:
            s.ehlo()
            s.starttls()
            s.ehlo()
            if smtp_user and smtp_pass:
                s.login(smtp_user, smtp_pass)
        else:
            # for other ports / servers - try login if provided
            if smtp_user and smtp_pass:
                s.login(smtp_user, smtp_pass)
        s.sendmail(from_addr, [to_addr], msg.as_string())
        print(f"Email (with .ics) sent to {to_addr}")
    finally:
        s.quit()


def generate_offer_text(candidate_name: str, role: str, salary_str: str, start_date: str) -> str:
    """Use OpenAI to generate a formal offer letter text. If no OpenAI key, use a simple template."""
    if OPENAI_API_KEY:
        prompt = (f"Write a short formal offer letter for {candidate_name} for the role {role}. "
                  f"Include compensation {salary_str} and start date {start_date}. "
                  "Include next steps and acceptance instructions (brief).")
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o",
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
            "Next steps: please reply to this email to accept or decline the offer.\n\n"
            "Regards,\nCompany-A HR")


# ----------------- Core demo flows -----------------
def schedule_interview_and_send_invite(candidate_email: str, candidate_name: str,
                                       topic: str, start_dt_utc: datetime, duration_mins: int = 30):
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

    # send email
    body = (f"Hi {candidate_name},\n\nYou are invited for an interview for the role: {topic}.\n"
            f"Scheduled (UTC): {start_dt_utc.isoformat()} for {duration_mins} minutes.\n"
            "Please find the attached calendar invite.\n\nRegards,\nCompany-A HR")
    try:
        send_email_with_ics(FROM_EMAIL, candidate_email, f"Interview Invitation — {topic}", body, ics)
    except Exception as e:
        print("Failed to send invite:", e)

    print(f"Interview record saved (id={interview_id}, uid={uid})")
    return interview_id, uid


def send_offer_email(candidate_email: str, candidate_name: str, role: str, salary_str: str, start_date: str):
    # create DB entry
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO offers (candidate_email, candidate_name, role, salary, offer_text, offer_sent_at, offer_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (candidate_email, candidate_name, role, salary_str, "", datetime.now(timezone.utc).isoformat(), "pending"))
        conn.commit()
        offer_id = cur.lastrowid

    # generate offer text
    offer_text = generate_offer_text(candidate_name, role, salary_str, start_date)

    # update DB with offer_text & sent time
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE offers SET offer_text = ?, offer_sent_at = ?, offer_status = ? WHERE id = ?",
                    (offer_text, datetime.now(timezone.utc).isoformat(), "sent", offer_id))
        conn.commit()

    # compose email body (simple — ask candidate to reply to accept)
    body = (f"Dear {candidate_name},\n\n{offer_text}\n\n"
            "To accept this offer, please reply to this email with 'I accept'.\n\n"
            "Regards,\nCompany-A HR")

    # send email
    msg = MIMEText(body)
    msg['Subject'] = f"Offer Letter — {role} (Company-A)"
    msg['From'] = FROM_EMAIL
    msg['To'] = candidate_email

    try:
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        if SMTP_PORT == 587 and SMTP_USER and SMTP_PASS:
            s.ehlo()
            s.starttls()
            s.ehlo()
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
    candidate_email = "142402011@smail.iitpkd.ac.in"   # demo recipient
    candidate_name = "Student A"
    topic = "Data Analyst"
    start_dt = datetime.now(timezone.utc) + timedelta(days=1, hours=1)
    schedule_interview_and_send_invite(candidate_email, candidate_name, topic, start_dt, duration_mins=30)


def demo_offer():
    create_tables()
    candidate_email = "142402011@smail.iitpkd.ac.in"   # demo recipient
    candidate_name = "Student A"
    role = "Data Analyst"
    salary = "8 LPA"
    start_date = (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()
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
