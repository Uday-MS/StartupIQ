# =============================================================================
# AUTH MODULE — Authentication routes (Blueprint)
# Handles: Email auth, Google OAuth, Save Startups, Recommendations,
#          Forgot Password, Email Verification, OTP Verification
# =============================================================================
import os
import re
import secrets
import hashlib
import random
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from db import get_conn, put_conn

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

auth_bp = Blueprint("auth", __name__)


# =============================================================================
# HELPERS
# =============================================================================

# ---------------------------------------------------------------------------
# PASSWORD POLICY — Enforced on signup, reset, and change
# ---------------------------------------------------------------------------
def _validate_password(password):
    """Validate password against strong password policy.

    Requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character (!@#$%^&*()_+-=)

    Returns (is_valid, error_message).
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least 1 uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least 1 lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least 1 number"
    if not re.search(r'[!@#$%^&*()_+\-=]', password):
        return False, "Password must contain at least 1 special character (!@#$%^&*()_+-=)"
    return True, ""


# ---------------------------------------------------------------------------
# EMAIL SENDER — Generic SMTP helper for all email types
# ---------------------------------------------------------------------------
def _send_email(to_email, subject, body_text):
    """Send an email via SMTP (Gmail). Returns True on success."""
    print(f"📧 Sending email to: {to_email} — Subject: {subject}")

    email_user = os.getenv("EMAIL_USER", "")
    email_pass = os.getenv("EMAIL_PASS", "")

    if not email_user or not email_pass:
        print("⚠️  EMAIL_USER / EMAIL_PASS not set in .env — cannot send email")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        print(f"Connecting to smtp.gmail.com:587 (TLS) as {email_user}")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_user, email_pass)
            server.send_message(msg)
        print(f"✅ Email sent successfully to: {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Email authentication failed: {e}")
        print("   Check EMAIL_USER and EMAIL_PASS in .env (use App Password for Gmail)")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error sending email: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def _send_reset_email(to_email, token):
    """Send a password-reset email (uses generic sender)."""
    reset_link = f"{BASE_URL}/reset-password/{token}"
    return _send_email(
        to_email,
        "StartupIQ — Password Reset",
        f"""\
Hello,

We received a request to reset your password for StartupIQ.

Click the link below to reset your password:

{reset_link}

This link will expire in 15 minutes.

If you did not request this, please ignore this email.

Regards,
StartupIQ Team
""",
    )


def _send_verification_email(to_email, token):
    """Send an email verification link."""
    verify_link = f"{BASE_URL}/verify-email/{token}"
    return _send_email(
        to_email,
        "StartupIQ — Verify Your Email",
        f"""\
Hello,

Welcome to StartupIQ! Please verify your email address.

Click the link below to verify your account:

{verify_link}

This link will expire in 24 hours.

If you did not create an account, please ignore this email.

Regards,
StartupIQ Team
""",
    )


def _send_otp_email(to_email, otp_code):
    """Send an OTP code via email."""
    return _send_email(
        to_email,
        "StartupIQ — Your Verification Code",
        f"""\
Hello,

Your StartupIQ verification code is:

    {otp_code}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email.

Regards,
StartupIQ Team
""",
    )


# ---------------------------------------------------------------------------
# OTP HELPERS
# ---------------------------------------------------------------------------
def _generate_otp():
    """Generate a 6-digit numeric OTP."""
    return str(random.randint(100000, 999999))


def _hash_otp(otp_code):
    """Hash OTP for secure storage (SHA-256)."""
    return hashlib.sha256(otp_code.encode()).hexdigest()



# ---------------------------------------------------------------------------
# SIGNUP — POST /signup
# ---------------------------------------------------------------------------
@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Create a new user account with email verification."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    # --- Validation ---
    errors = []
    if not username or len(username) < 2:
        errors.append("Username must be at least 2 characters")
    if not email or "@" not in email:
        errors.append("Valid email is required")

    # Strong password policy
    pw_valid, pw_error = _validate_password(password)
    if not pw_valid:
        errors.append(pw_error)

    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    # --- Store in DB ---
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Check for duplicate email
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            return jsonify({"error": "An account with this email already exists"}), 409

        # Hash password and generate verification token
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
        verification_token = secrets.token_urlsafe(32)
        verification_expiry = datetime.utcnow() + timedelta(hours=24)

        cur.execute(
            """INSERT INTO users (username, email, password_hash, is_verified,
               verification_token, verification_expiry)
               VALUES (%s, %s, %s, FALSE, %s, %s) RETURNING id""",
            (username, email, pw_hash, verification_token, verification_expiry),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()

        # Set session (allow usage while unverified)
        session["user_id"] = user_id
        session["username"] = username

        # Send verification email (non-blocking — signup succeeds even if email fails)
        email_sent = _send_verification_email(email, verification_token)
        print(f"Signup: User '{username}' (ID: {user_id}) created. Verification email sent: {email_sent}")

        return jsonify({
            "success": True,
            "message": "Account created successfully! Please check your email to verify your account.",
            "user": {"id": user_id, "username": username, "email": email},
            "verification_email_sent": email_sent,
        }), 201


    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# LOGIN — POST /login
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate an existing user."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, google_id FROM users WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
        cur.close()

        if not row:
            return jsonify({"error": "No account found with this email"}), 401

        user_id, username, pw_hash, google_id = row

        # If user signed up via Google and has no password
        if google_id and not pw_hash:
            return jsonify({"error": "This account uses Google sign-in. Please use 'Continue with Google'."}), 401

        if not check_password_hash(pw_hash, password):
            return jsonify({"error": "Incorrect password"}), 401

        # Set session
        session["user_id"] = user_id
        session["username"] = username

        return jsonify({
            "success": True,
            "message": f"Welcome back, {username}!",
            "user": {"id": user_id, "username": username, "email": email},
        })

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# LOGOUT — GET /logout
# ---------------------------------------------------------------------------
@auth_bp.route("/logout")
def logout():
    """Clear session and log the user out."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


# ---------------------------------------------------------------------------
# AUTH STATUS — GET /auth/status
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/status")
def auth_status():
    """Check if the user is currently logged in."""
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "user": {
                "id": session["user_id"],
                "username": session["username"],
            },
        })
    return jsonify({"logged_in": False})


# =============================================================================
# GOOGLE OAUTH — Authlib Implementation (production-safe, no PKCE issues)
# =============================================================================

from authlib.integrations.flask_client import OAuth

# OAuth instance — initialized lazily when blueprint is registered on the app
_oauth = None


def _get_oauth():
    """Get or initialize the Authlib OAuth client (lazy singleton)."""
    global _oauth
    if _oauth is not None:
        return _oauth

    from flask import current_app

    _oauth = OAuth(current_app)
    _oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    print("✅ Google OAuth client registered via Authlib")
    return _oauth


@auth_bp.route("/auth/google/login")
def google_login():
    """Redirect user to Google's OAuth consent screen."""
    print("Google Auth: Login route hit")

    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("⚠️  Google OAuth not configured — GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET missing in .env")
        return redirect("/?auth_error=google_not_configured")

    try:
        oauth = _get_oauth()
        redirect_uri = f"{BASE_URL}/auth/google/callback"
        print(f"Google Auth: Redirecting to Google consent screen (callback: {redirect_uri})")
        return oauth.google.authorize_redirect(redirect_uri)

    except Exception as e:
        print(f"❌ Google Auth setup error: {e}")
        import traceback
        traceback.print_exc()
        return redirect("/?auth_error=google_failed")


@auth_bp.route("/auth/google/callback")
def google_callback():
    """Handle Google OAuth callback."""
    print("Google Auth: Callback received")

    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("❌ Google Auth callback: credentials missing")
        return redirect("/?auth_error=google_not_configured")

    try:
        oauth = _get_oauth()

        # Exchange authorization code for token (Authlib handles this cleanly)
        token = oauth.google.authorize_access_token()
        print("Google Auth: Token exchange successful")

        # Extract user info from the ID token (OpenID Connect)
        userinfo = token.get("userinfo")
        if not userinfo:
            # Fallback: fetch from userinfo endpoint
            print("Google Auth: No userinfo in token, fetching from endpoint")
            userinfo = oauth.google.userinfo()

        google_id = userinfo.get("sub")
        email = (userinfo.get("email") or "").lower()
        name = userinfo.get("name") or email.split("@")[0]

        if not google_id or not email:
            print(f"❌ Google Auth: Missing user info — sub={google_id}, email={email}")
            return redirect("/?auth_error=google_failed")

        print(f"Google Auth: User info received — {email} (sub: {google_id})")

    except Exception as e:
        print(f"❌ Google Auth token exchange error: {e}")
        import traceback
        traceback.print_exc()
        return redirect("/?auth_error=google_failed")

    # --- Database logic (preserved exactly from original) ---
    conn = get_conn()
    try:
        cur = conn.cursor()

        # First check by google_id
        cur.execute("SELECT id, username FROM users WHERE google_id = %s", (google_id,))
        row = cur.fetchone()

        if row:
            # Existing Google user — log in
            user_id, username = row
            print(f"Google Auth: Existing user login — {username} (ID: {user_id})")
        else:
            # Check if email already exists (user signed up with email before)
            cur.execute("SELECT id, username FROM users WHERE email = %s", (email,))
            row = cur.fetchone()

            if row:
                # Link Google ID to existing account
                user_id, username = row
                cur.execute(
                    "UPDATE users SET google_id = %s WHERE id = %s",
                    (google_id, user_id),
                )
                print(f"Google Auth: Linked Google ID to existing account — {username} (ID: {user_id})")
            else:
                # Create new user (no password for Google users)
                cur.execute(
                    "INSERT INTO users (username, email, google_id) VALUES (%s, %s, %s) RETURNING id",
                    (name, email, google_id),
                )
                user_id = cur.fetchone()[0]
                username = name
                print(f"Google Auth: New user created — {username} (ID: {user_id})")

        conn.commit()
        cur.close()

        # Set session (preserved exactly)
        session["user_id"] = user_id
        session["username"] = username

        print(f"Google Auth: ✅ Success — user '{username}' (ID: {user_id}) logged in")
        return redirect("/")

    except Exception as e:
        conn.rollback()
        print(f"❌ Google Auth DB error: {e}")
        import traceback
        traceback.print_exc()
        return redirect("/?auth_error=google_failed")
    finally:
        put_conn(conn)


# Keep legacy placeholder route for backward compatibility
@auth_bp.route("/auth/google")
def google_auth_legacy():
    """Redirect to the real Google login flow."""
    return redirect(url_for("auth.google_login"))


# =============================================================================
# SAVE STARTUP — Full CRUD with industry/country for recommendations
# =============================================================================

# ---------------------------------------------------------------------------
# SAVE STARTUP — POST /api/save-startup
# ---------------------------------------------------------------------------
@auth_bp.route("/api/save-startup", methods=["POST"])
def save_startup():
    """Save a startup to the user's collection. Requires login."""
    if "user_id" not in session:
        return jsonify({"error": "Login required to save startups", "login_required": True}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    startup_name = (data.get("startup_name") or "").strip()
    if not startup_name:
        return jsonify({"error": "Startup name is required"}), 400

    industry = (data.get("industry") or "").strip()
    country = (data.get("country") or "").strip()
    funding = data.get("funding", 0)

    # Ensure funding is numeric
    try:
        funding = float(funding)
    except (ValueError, TypeError):
        funding = 0.0

    user_id = session["user_id"]
    print(f"Saving startup '{startup_name}' for user: {user_id}")

    conn = get_conn()
    try:
        cur = conn.cursor()

        # Check for duplicate
        cur.execute(
            "SELECT id FROM saved_startups WHERE user_id = %s AND startup_name = %s",
            (user_id, startup_name),
        )
        if cur.fetchone():
            cur.close()
            print(f"Startup '{startup_name}' already saved for user: {user_id}")
            return jsonify({"error": "Startup already saved"}), 409

        cur.execute(
            """INSERT INTO saved_startups (user_id, startup_name, industry, country, funding)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (user_id, startup_name, industry, country, funding),
        )
        saved_id = cur.fetchone()[0]
        conn.commit()
        cur.close()

        print(f"Startup saved for user: {user_id} — '{startup_name}' (ID: {saved_id})")
        return jsonify({
            "success": True,
            "message": f"'{startup_name}' saved successfully",
            "id": saved_id,
        }), 201

    except Exception as e:
        conn.rollback()
        print(f"❌ Save startup error for user {user_id}: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# UNSAVE STARTUP — DELETE /api/unsave-startup
# ---------------------------------------------------------------------------
@auth_bp.route("/api/unsave-startup", methods=["DELETE"])
def unsave_startup():
    """Remove a saved startup by name. Requires login."""
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True)
    startup_name = (data.get("startup_name") or "").strip() if data else ""

    if not startup_name:
        return jsonify({"error": "Startup name is required"}), 400

    user_id = session["user_id"]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM saved_startups WHERE user_id = %s AND startup_name = %s",
            (user_id, startup_name),
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()

        if deleted == 0:
            return jsonify({"error": "Startup not found in your saved list"}), 404

        return jsonify({"success": True, "message": f"'{startup_name}' removed"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# GET SAVED STARTUPS — GET /api/saved-startups
# ---------------------------------------------------------------------------
@auth_bp.route("/api/saved-startups")
def get_saved_startups():
    """Return the logged-in user's saved startups."""
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    user_id = session["user_id"]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, startup_name, industry, country, funding, created_at
               FROM saved_startups WHERE user_id = %s ORDER BY created_at DESC""",
            (user_id,),
        )
        rows = cur.fetchall()
        cur.close()

        startups = [
            {
                "id": r[0],
                "startup_name": r[1],
                "industry": r[2] or "",
                "country": r[3] or "",
                "funding": r[4] or 0,
                "saved_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]

        return jsonify({"startups": startups})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# DELETE SAVED STARTUP — DELETE /api/save-startup/<id>
# ---------------------------------------------------------------------------
@auth_bp.route("/api/save-startup/<int:startup_id>", methods=["DELETE"])
def delete_saved_startup(startup_id):
    """Remove a saved startup by ID. Requires login + ownership."""
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    user_id = session["user_id"]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM saved_startups WHERE id = %s AND user_id = %s",
            (startup_id, user_id),
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()

        if deleted == 0:
            return jsonify({"error": "Startup not found or not yours"}), 404

        return jsonify({"success": True, "message": "Startup removed"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# RECOMMENDATION SYSTEM — Handled by app.py (uses pandas for filtering)
# The /api/recommendations route is defined in app.py where the DataFrame
# is available for proper filtering and recommendation generation.
# =============================================================================


# =============================================================================
# FORGOT PASSWORD — Token-based email reset
# =============================================================================

# ---------------------------------------------------------------------------
# POST /forgot-password — Generate token and send email
# ---------------------------------------------------------------------------
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Generate a reset token and send email."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, google_id, password_hash FROM users WHERE email = %s", (email,))
        row = cur.fetchone()

        if not row:
            # Don't reveal whether account exists (security)
            return jsonify({
                "success": True,
                "message": "If an account with that email exists, a reset link has been sent.",
            })

        user_id, google_id, pw_hash = row

        # If user signed up via Google only
        if google_id and not pw_hash:
            return jsonify({
                "error": "This account uses Google sign-in. Password reset is not available.",
            }), 400

        # Generate token
        token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(minutes=15)

        cur.execute(
            "UPDATE users SET reset_token = %s, token_expiry = %s WHERE id = %s",
            (token, expiry, user_id),
        )
        conn.commit()
        cur.close()

        # Send email
        email_sent = _send_reset_email(email, token)

        if email_sent:
            return jsonify({
                "success": True,
                "message": "Password reset link has been sent to your email.",
            })
        else:
            # Email sending failed — inform the user clearly
            email_user = os.getenv("EMAIL_USER", "")
            if not email_user:
                return jsonify({
                    "success": False,
                    "error": "Email sending is not configured on the server. Please contact the administrator or set EMAIL_USER and EMAIL_PASS in .env.",
                    "dev_token": token,  # Remove in production
                }), 503
            else:
                return jsonify({
                    "success": False,
                    "error": "Failed to send reset email. Please try again later or check server logs.",
                    "dev_token": token,  # Remove in production
                }), 500

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# GET /reset-password/<token> — Validate token and show reset form
# ---------------------------------------------------------------------------
@auth_bp.route("/reset-password/<token>", methods=["GET"])
def reset_password_form(token):
    """Validate the reset token and show the reset form."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE reset_token = %s AND token_expiry > %s",
            (token, datetime.utcnow()),
        )
        row = cur.fetchone()
        cur.close()

        if not row:
            return render_template("reset_password.html", valid=False, token=token)

        return render_template("reset_password.html", valid=True, token=token)

    except Exception as e:
        return render_template("reset_password.html", valid=False, token=token)
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# POST /reset-password/<token> — Set new password
# ---------------------------------------------------------------------------
@auth_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password_submit(token):
    """Validate token and update password."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    password = (data.get("password") or "").strip()

    # Strong password policy
    pw_valid, pw_error = _validate_password(password)
    if not pw_valid:
        return jsonify({"error": pw_error}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE reset_token = %s AND token_expiry > %s",
            (token, datetime.utcnow()),
        )
        row = cur.fetchone()

        if not row:
            cur.close()
            return jsonify({"error": "Invalid or expired reset link"}), 400

        user_id = row[0]
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")

        # Update password and clear token
        cur.execute(
            "UPDATE users SET password_hash = %s, reset_token = NULL, token_expiry = NULL WHERE id = %s",
            (pw_hash, user_id),
        )
        conn.commit()
        cur.close()

        print(f"Password Reset: ✅ Password updated for user ID {user_id}")
        return jsonify({
            "success": True,
            "message": "Password reset successfully! You can now login.",
        })

    except Exception as e:
        conn.rollback()
        print(f"❌ Password reset error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# EMAIL VERIFICATION — Token-based email ownership verification
# =============================================================================

# ---------------------------------------------------------------------------
# GET /verify-email/<token> — Verify email via link
# ---------------------------------------------------------------------------
@auth_bp.route("/verify-email/<token>", methods=["GET"])
def verify_email(token):
    """Verify a user's email address via token link."""
    print(f"Email Verification: Token received — {token[:8]}...")

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, is_verified FROM users WHERE verification_token = %s AND verification_expiry > %s",
            (token, datetime.utcnow()),
        )
        row = cur.fetchone()

        if not row:
            print("Email Verification: ❌ Invalid or expired token")
            cur.close()
            return render_template("verify_email.html", success=False,
                                   message="This verification link is invalid or has expired.")

        user_id, username, is_verified = row

        if is_verified:
            print(f"Email Verification: User {user_id} already verified")
            cur.close()
            return render_template("verify_email.html", success=True,
                                   message="Your email is already verified! You can close this page.")

        # Mark as verified and clear token
        cur.execute(
            "UPDATE users SET is_verified = TRUE, verification_token = NULL, verification_expiry = NULL WHERE id = %s",
            (user_id,),
        )
        conn.commit()
        cur.close()

        print(f"Email Verification: ✅ User '{username}' (ID: {user_id}) verified successfully")
        return render_template("verify_email.html", success=True,
                               message="Your email has been verified successfully!")

    except Exception as e:
        print(f"❌ Email verification error: {e}")
        return render_template("verify_email.html", success=False,
                               message="An error occurred. Please try again.")
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# POST /auth/resend-verification — Resend verification email
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/resend-verification", methods=["POST"])
def resend_verification():
    """Resend verification email for the logged-in user."""
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    user_id = session["user_id"]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT email, is_verified FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()

        if not row:
            cur.close()
            return jsonify({"error": "User not found"}), 404

        email, is_verified = row

        if is_verified:
            cur.close()
            return jsonify({"success": True, "message": "Email is already verified."})

        # Generate new token
        verification_token = secrets.token_urlsafe(32)
        verification_expiry = datetime.utcnow() + timedelta(hours=24)

        cur.execute(
            "UPDATE users SET verification_token = %s, verification_expiry = %s WHERE id = %s",
            (verification_token, verification_expiry, user_id),
        )
        conn.commit()
        cur.close()

        email_sent = _send_verification_email(email, verification_token)
        print(f"Resend Verification: User {user_id} — email sent: {email_sent}")

        if email_sent:
            return jsonify({"success": True, "message": "Verification email sent! Check your inbox."})
        else:
            return jsonify({"error": "Failed to send verification email. Please try again later."}), 500

    except Exception as e:
        conn.rollback()
        print(f"❌ Resend verification error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# OTP VERIFICATION — Secure 6-digit OTP via email
# =============================================================================

# ---------------------------------------------------------------------------
# POST /auth/send-otp — Generate and send OTP
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/send-otp", methods=["POST"])
def send_otp():
    """Generate and send a 6-digit OTP to the user's email."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, otp_last_sent FROM users WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()

        if not row:
            # Don't reveal whether account exists
            print(f"OTP: Requested for non-existent email — {email}")
            return jsonify({"success": True, "message": "If an account exists, an OTP has been sent."})

        user_id, otp_last_sent = row

        # Cooldown: prevent resend within 60 seconds
        if otp_last_sent:
            elapsed = (datetime.utcnow() - otp_last_sent).total_seconds()
            if elapsed < 60:
                remaining = int(60 - elapsed)
                print(f"OTP: Cooldown active for user {user_id} — {remaining}s remaining")
                return jsonify({
                    "error": f"Please wait {remaining} seconds before requesting a new code.",
                    "cooldown": remaining,
                }), 429

        # Generate OTP
        otp_code = _generate_otp()
        otp_hash = _hash_otp(otp_code)
        otp_expiry = datetime.utcnow() + timedelta(minutes=10)

        cur.execute(
            "UPDATE users SET otp_hash = %s, otp_expiry = %s, otp_attempts = 0, otp_last_sent = %s WHERE id = %s",
            (otp_hash, otp_expiry, datetime.utcnow(), user_id),
        )
        conn.commit()
        cur.close()

        # Send OTP email
        email_sent = _send_otp_email(email, otp_code)
        print(f"OTP: Generated for user {user_id} — sent: {email_sent}")

        if email_sent:
            return jsonify({"success": True, "message": "Verification code sent to your email."})
        else:
            return jsonify({"error": "Failed to send verification code. Please try again."}), 500

    except Exception as e:
        conn.rollback()
        print(f"❌ OTP send error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# POST /auth/verify-otp — Verify OTP code
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    """Verify a 6-digit OTP code."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    email = (data.get("email") or "").strip().lower()
    otp_code = (data.get("otp") or "").strip()

    if not email or not otp_code:
        return jsonify({"error": "Email and OTP code are required"}), 400

    if not otp_code.isdigit() or len(otp_code) != 6:
        return jsonify({"error": "OTP must be a 6-digit number"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, otp_hash, otp_expiry, otp_attempts FROM users WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()

        if not row:
            return jsonify({"error": "Invalid email or OTP"}), 401

        user_id, username, stored_hash, otp_expiry, otp_attempts = row

        # Check brute force (max 5 attempts)
        if otp_attempts and otp_attempts >= 5:
            print(f"OTP: ❌ Too many attempts for user {user_id}")
            # Clear OTP to force resend
            cur.execute(
                "UPDATE users SET otp_hash = NULL, otp_expiry = NULL, otp_attempts = 0 WHERE id = %s",
                (user_id,),
            )
            conn.commit()
            cur.close()
            return jsonify({"error": "Too many failed attempts. Please request a new code."}), 429

        # Check expiry
        if not otp_expiry or datetime.utcnow() > otp_expiry:
            print(f"OTP: ❌ Expired for user {user_id}")
            cur.close()
            return jsonify({"error": "OTP has expired. Please request a new code."}), 400

        # Check hash
        if not stored_hash or _hash_otp(otp_code) != stored_hash:
            # Increment attempts
            new_attempts = (otp_attempts or 0) + 1
            cur.execute(
                "UPDATE users SET otp_attempts = %s WHERE id = %s",
                (new_attempts, user_id),
            )
            conn.commit()
            cur.close()
            remaining = 5 - new_attempts
            print(f"OTP: ❌ Invalid code for user {user_id} — {remaining} attempts remaining")
            return jsonify({
                "error": f"Invalid code. {remaining} attempt(s) remaining.",
                "attempts_remaining": remaining,
            }), 401

        # OTP is valid — clear it (single use)
        cur.execute(
            "UPDATE users SET otp_hash = NULL, otp_expiry = NULL, otp_attempts = 0, is_verified = TRUE WHERE id = %s",
            (user_id,),
        )
        conn.commit()
        cur.close()

        # Set session
        session["user_id"] = user_id
        session["username"] = username

        print(f"OTP: ✅ Verified for user '{username}' (ID: {user_id})")
        return jsonify({
            "success": True,
            "message": "Verification successful!",
            "user": {"id": user_id, "username": username},
        })

    except Exception as e:
        conn.rollback()
        print(f"❌ OTP verification error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# CHANGE PASSWORD — For logged-in users
# =============================================================================

# ---------------------------------------------------------------------------
# POST /auth/change-password — Change password (requires current password)
# ---------------------------------------------------------------------------
@auth_bp.route("/auth/change-password", methods=["POST"])
def change_password():
    """Change password for the logged-in user."""
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    current_password = (data.get("current_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not current_password:
        return jsonify({"error": "Current password is required"}), 400

    # Strong password policy on new password
    pw_valid, pw_error = _validate_password(new_password)
    if not pw_valid:
        return jsonify({"error": pw_error}), 400

    user_id = session["user_id"]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT password_hash, google_id FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()

        if not row:
            cur.close()
            return jsonify({"error": "User not found"}), 404

        pw_hash, google_id = row

        # Google-only users cannot change password
        if google_id and not pw_hash:
            cur.close()
            return jsonify({"error": "This account uses Google sign-in. Password change is not available."}), 400

        # Verify current password
        if not check_password_hash(pw_hash, current_password):
            cur.close()
            print(f"Change Password: ❌ Wrong current password for user {user_id}")
            return jsonify({"error": "Current password is incorrect"}), 401

        # Update password
        new_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, user_id),
        )
        conn.commit()
        cur.close()

        print(f"Change Password: ✅ Password changed for user {user_id}")
        return jsonify({"success": True, "message": "Password changed successfully!"})

    except Exception as e:
        conn.rollback()
        print(f"❌ Change password error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# PASSWORD POLICY ENDPOINT — For frontend validation
# =============================================================================

@auth_bp.route("/auth/password-policy")
def password_policy():
    """Return password policy rules for frontend validation."""
    return jsonify({
        "rules": [
            {"id": "length", "label": "At least 8 characters", "regex": ".{8,}"},
            {"id": "uppercase", "label": "At least 1 uppercase letter", "regex": "[A-Z]"},
            {"id": "lowercase", "label": "At least 1 lowercase letter", "regex": "[a-z]"},
            {"id": "number", "label": "At least 1 number", "regex": "[0-9]"},
            {"id": "special", "label": "At least 1 special character (!@#$%^&*()_+-=)", "regex": "[!@#$%^&*()_+\\-=]"},
        ]
    })
