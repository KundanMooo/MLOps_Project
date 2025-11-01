import smtplib
import getpass

HOST = "smtp.gmail.com"
PORT = 587

FROM_EMAIL = "sumanpaljanta@gmail.com"
TO_EMAIL = "sumanpalpal24@gmail.com"
PASSWORD = getpass.getpass("Enter App Password: ")

# Email content must include "From", "To", and "Subject" headers separated by \n
MESSAGE = f"""From: {FROM_EMAIL}
To: {TO_EMAIL}
Subject: This is a testing mail

Hi,
This is a testing mail. Kindly ignore it.
"""

# Create SMTP session
smtp = smtplib.SMTP(HOST, PORT)

# Say hello to the server
status_code, response = smtp.ehlo()
print(f"[*] Echoing the server: {status_code} {response}")

# Start TLS encryption
status_code, response = smtp.starttls()
print(f"[*] Starting TLS connection: {status_code} {response}")

# Login to your Gmail account
status_code, response = smtp.login(FROM_EMAIL, PASSWORD)
print(f"[*] Logging in: {status_code} {response}")

# Send the email
smtp.sendmail(FROM_EMAIL, TO_EMAIL, MESSAGE)
print("[*] Email sent successfully!")

# Close the connection
smtp.quit()
