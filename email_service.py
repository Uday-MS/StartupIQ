# =============================================================================
# EMAIL SERVICE — Resend API Integration
# Replaces Gmail SMTP for reliable cloud email delivery (Railway/Render safe)
# =============================================================================
import os
import resend
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
FROM_EMAIL = "StartupIQ <onboarding@resend.dev>"


def _init_resend():
    """Initialize Resend SDK with API key."""
    if not RESEND_API_KEY:
        print("⚠️  RESEND_API_KEY not configured — email sending disabled")
        return False
    resend.api_key = RESEND_API_KEY
    return True


# ---------------------------------------------------------------------------
# CORE SENDER — All email functions route through this
# ---------------------------------------------------------------------------
def send_email(to_email, subject, html_body):
    """Send an email via Resend API.

    Returns True on success, False on any failure (never raises).
    This matches the contract of the old SMTP-based _send_email().
    """
    print(f"📧 Sending email to: {to_email} — Subject: {subject}")

    if not _init_resend():
        return False

    try:
        params = {
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }

        response = resend.Emails.send(params)
        email_id = response.get("id", "unknown") if isinstance(response, dict) else getattr(response, "id", "unknown")
        print(f"✅ Email sent successfully to: {to_email} (ID: {email_id})")
        return True

    except Exception as e:
        print(f"❌ Resend API error ({type(e).__name__}): {e}")
        return False


# ---------------------------------------------------------------------------
# HTML EMAIL TEMPLATES
# ---------------------------------------------------------------------------

def _otp_html(otp_code):
    """Professional HTML template for OTP verification emails."""
    return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:32px 40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">StartupIQ</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:40px;">
              <h2 style="margin:0 0 16px;color:#1a1a2e;font-size:20px;font-weight:600;">Verification Code</h2>
              <p style="margin:0 0 24px;color:#4a4a68;font-size:15px;line-height:1.6;">
                Use the code below to complete your verification. This code expires in <strong>10 minutes</strong>.
              </p>
              <!-- OTP Code -->
              <div style="background-color:#f0f0ff;border:2px dashed #6366f1;border-radius:8px;padding:20px;text-align:center;margin:0 0 24px;">
                <span style="font-size:36px;font-weight:700;letter-spacing:8px;color:#6366f1;font-family:monospace;">{otp_code}</span>
              </div>
              <p style="margin:0;color:#8888a0;font-size:13px;line-height:1.5;">
                If you did not request this code, you can safely ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;background-color:#fafafc;border-top:1px solid #eeeef2;text-align:center;">
              <p style="margin:0;color:#a0a0b8;font-size:12px;">&copy; StartupIQ. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _reset_html(reset_link):
    """Professional HTML template for password reset emails."""
    return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:32px 40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">StartupIQ</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:40px;">
              <h2 style="margin:0 0 16px;color:#1a1a2e;font-size:20px;font-weight:600;">Password Reset</h2>
              <p style="margin:0 0 24px;color:#4a4a68;font-size:15px;line-height:1.6;">
                We received a request to reset your password. Click the button below to set a new password. This link expires in <strong>15 minutes</strong>.
              </p>
              <!-- CTA Button -->
              <div style="text-align:center;margin:0 0 24px;">
                <a href="{reset_link}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:8px;font-size:15px;font-weight:600;">Reset Password</a>
              </div>
              <p style="margin:0 0 16px;color:#8888a0;font-size:13px;line-height:1.5;">
                If the button doesn't work, copy and paste this link into your browser:
              </p>
              <p style="margin:0 0 24px;word-break:break-all;color:#6366f1;font-size:13px;">{reset_link}</p>
              <p style="margin:0;color:#8888a0;font-size:13px;line-height:1.5;">
                If you did not request a password reset, please ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;background-color:#fafafc;border-top:1px solid #eeeef2;text-align:center;">
              <p style="margin:0;color:#a0a0b8;font-size:12px;">&copy; StartupIQ. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _verification_html(verify_link):
    """Professional HTML template for email verification."""
    return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:32px 40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">StartupIQ</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:40px;">
              <h2 style="margin:0 0 16px;color:#1a1a2e;font-size:20px;font-weight:600;">Verify Your Email</h2>
              <p style="margin:0 0 24px;color:#4a4a68;font-size:15px;line-height:1.6;">
                Welcome to StartupIQ! Please verify your email address by clicking the button below. This link expires in <strong>24 hours</strong>.
              </p>
              <!-- CTA Button -->
              <div style="text-align:center;margin:0 0 24px;">
                <a href="{verify_link}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:8px;font-size:15px;font-weight:600;">Verify Email</a>
              </div>
              <p style="margin:0 0 16px;color:#8888a0;font-size:13px;line-height:1.5;">
                If the button doesn't work, copy and paste this link into your browser:
              </p>
              <p style="margin:0 0 24px;word-break:break-all;color:#6366f1;font-size:13px;">{verify_link}</p>
              <p style="margin:0;color:#8888a0;font-size:13px;line-height:1.5;">
                If you did not create an account, please ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;background-color:#fafafc;border-top:1px solid #eeeef2;text-align:center;">
              <p style="margin:0;color:#a0a0b8;font-size:12px;">&copy; StartupIQ. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# PUBLIC API — These match the old function signatures from auth.py
# ---------------------------------------------------------------------------

def send_otp_email(to_email, otp_code):
    """Send an OTP verification code via email.

    Args:
        to_email: Recipient email address
        otp_code: 6-digit OTP string

    Returns:
        True on success, False on failure
    """
    print(f"📧 OTP delivery: Sending code to {to_email}")
    return send_email(
        to_email,
        "StartupIQ — Your Verification Code",
        _otp_html(otp_code),
    )


def send_reset_email(to_email, token):
    """Send a password reset email with a secure link.

    Args:
        to_email: Recipient email address
        token: URL-safe reset token

    Returns:
        True on success, False on failure
    """
    reset_link = f"{BASE_URL}/reset-password/{token}"
    print(f"📧 Password reset: Sending link to {to_email}")
    return send_email(
        to_email,
        "StartupIQ — Password Reset",
        _reset_html(reset_link),
    )


def send_verification_email(to_email, token):
    """Send an email verification link.

    Args:
        to_email: Recipient email address
        token: URL-safe verification token

    Returns:
        True on success, False on failure
    """
    verify_link = f"{BASE_URL}/verify-email/{token}"
    print(f"📧 Email verification: Sending link to {to_email}")
    return send_email(
        to_email,
        "StartupIQ — Verify Your Email",
        _verification_html(verify_link),
    )
