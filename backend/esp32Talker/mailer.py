import smtplib
from email.message import EmailMessage
import os

from dotenv import load_dotenv

def send_email(to_email: str, title: str, body: str) -> None:
    """
    Sends an email using an SMTP server.
    
    Parameters:
    - to_email (str): Email address to send to.
    - title (str): Title (subject) of the email.
    - body (str): Body content of the email.
    """
    load_dotenv()  # Load environment variables from .env file
    # Configuration (Update these with your actual SMTP server details)
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587  # Common port for TLS
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

    # Construct the email message
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg.set_content(body)

    try:
        # Connect to the SMTP server and send the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Upgrade the connection to secure (TLS)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            
        print(f"Success: Email sent to {to_email}")
        
    except Exception as e:
        print(f"Error: Failed to send email. Details: {e}")