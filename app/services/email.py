import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def _configured() -> bool:
    return bool(settings.smtp_user and settings.smtp_password and settings.alert_email)


def send_alert(subject: str, body: str) -> None:
    """Send a plain-text alert via Gmail SMTP. Silent no-op if SMTP is not configured."""
    if not _configured():
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.smtp_user
    msg["To"]      = settings.alert_email
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, settings.alert_email, msg.as_string())


def send_red_flag_alert(symptoms: list[str]) -> None:
    symptom_list = "\n".join(f"  - {s}" for s in symptoms)
    send_alert(
        subject="🚨 MigraineTackler: Red Flag Symptoms Detected",
        body=(
            "Red flag symptoms were detected in your latest log entry.\n\n"
            f"Matched symptoms:\n{symptom_list}\n\n"
            "Please seek immediate medical attention if these symptoms are severe or new.\n"
            "Do not ignore these warning signs.\n\n"
            "— MigraineTackler"
        ),
    )


def send_moh_alert(triptan_days: int, nsaid_days: int) -> None:
    send_alert(
        subject="⚠️ MigraineTackler: Medication Overuse Warning",
        body=(
            "You've reached the medication overuse headache (MOH) threshold this month.\n\n"
            f"  Triptan use : {triptan_days} days in the last 30 days (threshold: 10)\n"
            f"  NSAID use   : {nsaid_days} days in the last 30 days (threshold: 15)\n\n"
            "Medication overuse is one of the most common causes of chronic daily headache.\n"
            "Please discuss this with your doctor or neurologist.\n\n"
            "— MigraineTackler"
        ),
    )
