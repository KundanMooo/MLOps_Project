import os
from dotenv import load_dotenv
load_dotenv()

import sqlite3
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText

# ----------------- ENV CONFIG -----------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "no-reply@example.com")

DB_PATH = os.getenv("DB_PATH", "resumes.db")


# ----------------- DATABASE -----------------
def create_tables():
    """Create the offers table if not exists."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
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
    print("✅ Offer table ready.")


# ----------------- OFFER GENERATION (Static Template) -----------------
def generate_offer_text(candidate_name: str, role: str, salary_str: str, start_date: str) -> str:
    """Generate a simple static offer letter text without using any LLM."""
    return (
        f"Dear {candidate_name},\n\n"
        f"We are pleased to inform you that you have been selected for the position of {role} at Company-A.\n"
        f"Your compensation will be {salary_str}, and your start date is {start_date}.\n\n"
        f"Please reply to this email with 'I accept' to confirm your acceptance.\n\n"
        f"Regards,\nCompany-A HR"
    )


# ----------------- EMAIL SENDER -----------------
def send_offer_email(candidate_email: str, candidate_name: str, role: str, salary_str: str, start_date: str):
    """Compose and send the offer letter via SMTP."""
    # Create offer letter text
    offer_text = generate_offer_text(candidate_name, role, salary_str, start_date)

    # Save record in DB
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO offers (candidate_email, candidate_name, role, salary, offer_text, offer_sent_at, offer_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (candidate_email, candidate_name, role, salary_str, offer_text,
              datetime.now(timezone.utc).isoformat(), "sent"))
        conn.commit()
        offer_id = cur.lastrowid

    # Send email
    msg = MIMEText(offer_text)
    msg['Subject'] = f"🎉 Offer Letter — Company-A"
    msg['From'] = FROM_EMAIL
    msg['To'] = candidate_email

    try:
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        s.ehlo()
        if SMTP_PORT == 587:
            s.starttls()
            s.ehlo()
        if SMTP_USER and SMTP_PASS:
            s.login(SMTP_USER, SMTP_PASS)

        s.sendmail(FROM_EMAIL, [candidate_email], msg.as_string())
        s.quit()

        print(f"✅ Offer email sent to {candidate_name} ({candidate_email}) [Offer ID: {offer_id}]")

    except Exception as e:
        print(f"❌ Failed to send email to {candidate_email}: {e}")


# ----------------- MAIN FUNCTION -----------------
def send_offers(candidates, role="Data Analyst", salary="8 LPA"):
    """
    Send offer letters to all selected candidates.
    Args:
        candidates (list): [{'name': 'John Doe', 'email': 'john@example.com'}, {...}]
        role (str): Job role (auto-filled from JD output)
        salary (str): Salary info
    """
    create_tables()
    start_date = (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()

    for cand in candidates:
        name = cand.get("name")
        email = cand.get("email")

        if not email:
            print(f"⚠️ Skipping {name} (no email provided)")
            continue

        print(f"\n📩 Sending offer to {name} ({email}) for role: {role}")
        send_offer_email(candidate_email=email, candidate_name=name,
                         role=role, salary_str=salary, start_date=start_date)
