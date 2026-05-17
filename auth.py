# =============================================================================
# AUTH MODULE — Authentication routes (Blueprint)
# Handles: Email auth, Google OAuth, Save Startups, Recommendations,
#          Forgot Password with email reset
# =============================================================================
import os
import secrets
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

def _send_reset_email(to_email, token):
    """Send a password-reset email via SMTP (Gmail)."""
    print(f"Sending email to: {to_email}")

    email_user = os.getenv("EMAIL_USER", "")
    email_pass = os.getenv("EMAIL_PASS", "")

    if not email_user or not email_pass:
        print("⚠️  EMAIL_USER / EMAIL_PASS not set in .env — cannot send email")
        print("   To enable email sending, set EMAIL_USER and EMAIL_PASS in .env")
        print("   Using smtp.gmail.com on port 587 with TLS")
        return False

    reset_link = f"http://localhost:5000/reset-password/{token}"

    msg = EmailMessage()
    msg["Subject"] = "StartupIQ Password Reset"
    msg["From"] = email_user
    msg["To"] = to_email
    msg.set_content(f"""\
Hello,

We received a request to reset your password for StartupIQ.

Click the link below to reset your password:

{reset_link}

This link will expire in 15 minutes.

If you did not request this, please ignore this email.

Regards,
StartupIQ Team
""")

    try:
        print(f"Connecting to smtp.gmail.com:587 (TLS) as {email_user}")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_user, email_pass)
            server.send_message(msg)
        print(f"Email sent successfully to: {to_email}")
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


# ---------------------------------------------------------------------------
# SIGNUP — POST /signup
# ---------------------------------------------------------------------------
@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Create a new user account."""
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
    if not password or len(password) < 6:
        errors.append("Password must be at least 6 characters")

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

        # Hash password and insert
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (username, email, pw_hash),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()

        # Set session
        session["user_id"] = user_id
        session["username"] = username

        return jsonify({
            "success": True,
            "message": "Account created successfully",
            "user": {"id": user_id, "username": username, "email": email},
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
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

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

        return jsonify({
            "success": True,
            "message": "Password reset successfully! You can now login.",
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)
