import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings


def send_activation_email(to_email: str, full_name: str, username: str, activation_url: str) -> bool:
    settings = get_settings()
    
    subject = "🔑 Complete Your Claims Guard AI Corporate Account Setup"
    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
          <div style="background-color: #0f172a; color: #ffffff; padding: 20px; text-align: center;">
            <h2 style="margin: 0;">Claims Guard AI</h2>
            <p style="margin: 4px 0 0; font-size: 13px; color: #94a3b8;">Enterprise Account Setup Notice</p>
          </div>
          <div style="padding: 24px;">
            <p>Hello <strong>{full_name}</strong>,</p>
            <p>An enterprise staff profile has been provisioned for you on the Claims Guard platform.</p>
            
            <div style="background-color: #f8fafc; border-left: 4px solid #0f172a; padding: 12px 16px; margin: 16px 0;">
              <p style="margin: 0; font-size: 14px;"><strong>Generated Username:</strong> <code style="font-size: 16px; font-weight: bold; background: #e2e8f0; padding: 2px 6px; border-radius: 4px;">{username}</code></p>
              <p style="margin: 4px 0 0; font-size: 13px; color: #64748b;">(Naming rule: First 2 letters of first name + Last name)</p>
            </div>

            <p>Please click the button below to establish your permanent corporate password and activate your account:</p>

            <div style="text-align: center; margin: 24px 0;">
              <a href="{activation_url}" style="background-color: #16a34a; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                Set Up Permanent Password &rarr;
              </a>
            </div>

            <p style="font-size: 12px; color: #64748b;">If the button does not work, copy and paste this link into your browser:<br/>
            <a href="{activation_url}" style="color: #2563eb;">{activation_url}</a></p>

            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
            <p style="font-size: 11px; color: #94a3b8; text-align: center;">This is an automated system notification from Claims Guard AI. Do not reply to this email.</p>
          </div>
        </div>
      </body>
    </html>
    """
    
    if not settings.smtp_username or not settings.smtp_password:
        print(f"[SMTP NOTICE] Gmail SMTP credentials not configured. Activation email for {to_email} logged: {activation_url}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_email or settings.smtp_username
        msg["To"] = to_email
        
        part = MIMEText(body_html, "html")
        msg.attach(part)
        
        server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(msg["From"], [to_email], msg.as_string())
        server.quit()
        print(f"Successfully sent Gmail activation email to {to_email}")
        return True
    except Exception as e:
        print(f"Error sending Gmail email to {to_email}: {e}")
        return False
