# =============================================================================
# JWT AUTH MODULE — JWT Access Tokens + Refresh Token Architecture
# Provides: token creation, validation, rotation, revocation, cleanup
# Works alongside existing session authentication (hybrid model)
# =============================================================================
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import request, jsonify, session

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
# Use JWT_SECRET_KEY if set, otherwise fall back to SECRET_KEY
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY", "fallback-dev-key")
JWT_ALGORITHM = "HS256"

# Token lifetimes
ACCESS_TOKEN_EXPIRY_MINUTES = 15
REFRESH_TOKEN_EXPIRY_DAYS = 30


# =============================================================================
# ACCESS TOKEN — Short-lived JWT (15 minutes)
# =============================================================================

def create_access_token(user_id, username):
    """Create a short-lived JWT access token.

    Payload includes user_id, username, token_type, issued-at, and expiry.
    Signed with SECRET_KEY using HS256.

    Returns the encoded JWT string.
    """
    now = datetime.utcnow()
    payload = {
        "user_id": user_id,
        "username": username,
        "token_type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES),
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    print(f"JWT: Access token created for user {user_id} (expires: {ACCESS_TOKEN_EXPIRY_MINUTES}m)")
    return token


def decode_access_token(token):
    """Decode and validate a JWT access token.

    Returns the payload dict on success.
    Returns None on any failure (expired, invalid, wrong type).
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Verify token type
        if payload.get("token_type") != "access":
            print("JWT: ❌ Invalid token type — expected 'access'")
            return None

        return payload

    except jwt.ExpiredSignatureError:
        print("JWT: ❌ Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"JWT: ❌ Invalid access token — {e}")
        return None


# =============================================================================
# REFRESH TOKEN — Long-lived opaque token (30 days)
# =============================================================================

def _hash_token(token):
    """Hash a refresh token for secure storage (SHA-256)."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(user_id, conn, device_info=None):
    """Create a long-lived refresh token and store its hash in the database.

    Args:
        user_id: The user's ID
        conn: Database connection (from get_conn())
        device_info: Optional User-Agent or device identifier

    Returns the raw refresh token string (to be sent to the client).
    """
    # Generate cryptographically secure token (512-bit entropy)
    raw_token = secrets.token_urlsafe(64)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO refresh_tokens (user_id, token_hash, device_info, expires_at)
           VALUES (%s, %s, %s, %s)""",
        (user_id, token_hash, device_info or "unknown", expires_at),
    )
    conn.commit()
    cur.close()

    print(f"JWT: Refresh token created for user {user_id} (expires: {REFRESH_TOKEN_EXPIRY_DAYS}d)")
    return raw_token


def _validate_refresh_token(raw_token, conn):
    """Validate a refresh token against the database.

    Returns (token_row, error_message) tuple.
    token_row = (id, user_id, is_revoked) on success, None on failure.
    """
    token_hash = _hash_token(raw_token)

    cur = conn.cursor()
    cur.execute(
        """SELECT id, user_id, is_revoked, expires_at
           FROM refresh_tokens WHERE token_hash = %s""",
        (token_hash,),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        print("JWT: ❌ Refresh token not found")
        return None, "Invalid refresh token"

    token_id, user_id, is_revoked, expires_at = row

    # Check if token was revoked (possible token reuse attack)
    if is_revoked:
        print(f"JWT: ❌ Refresh token reuse detected for user {user_id} — revoking all tokens (security)")
        # SECURITY: Revoke all tokens for this user (family revocation)
        revoke_all_user_tokens(user_id, conn)
        return None, "Token has been revoked. All sessions invalidated for security."

    # Check expiry
    if datetime.utcnow() > expires_at:
        print(f"JWT: ❌ Refresh token expired for user {user_id}")
        return None, "Refresh token has expired. Please login again."

    return (token_id, user_id), None


def rotate_refresh_token(old_raw_token, conn, device_info=None):
    """Rotate a refresh token: validate old → revoke old → issue new pair.

    Implements token rotation to prevent replay attacks.
    If the old token has already been revoked (reuse detected), all user
    tokens are revoked as a security measure.

    Args:
        old_raw_token: The current refresh token string
        conn: Database connection
        device_info: Optional User-Agent or device identifier

    Returns:
        (access_token, new_refresh_token, user_id, username) on success
        (None, None, None, error_message) on failure
    """
    # Validate the old refresh token
    result, error = _validate_refresh_token(old_raw_token, conn)
    if result is None:
        return None, None, None, error

    token_id, user_id = result

    # Revoke the old refresh token (mark as used)
    cur = conn.cursor()
    cur.execute(
        "UPDATE refresh_tokens SET is_revoked = TRUE, revoked_at = %s WHERE id = %s",
        (datetime.utcnow(), token_id),
    )
    conn.commit()

    # Look up username for the access token payload
    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    user_row = cur.fetchone()
    cur.close()

    if not user_row:
        print(f"JWT: ❌ User {user_id} not found during token rotation")
        return None, None, None, "User not found"

    username = user_row[0]

    # Issue new token pair
    new_access_token = create_access_token(user_id, username)
    new_refresh_token = create_refresh_token(user_id, conn, device_info)

    print(f"JWT: Token rotation for user {user_id} — old token revoked, new pair issued")
    return new_access_token, new_refresh_token, user_id, None


# =============================================================================
# TOKEN REVOCATION
# =============================================================================

def revoke_refresh_token(raw_token, conn):
    """Revoke a single refresh token (logout current device).

    Returns True if a token was revoked, False if token not found.
    """
    token_hash = _hash_token(raw_token)

    cur = conn.cursor()
    cur.execute(
        "UPDATE refresh_tokens SET is_revoked = TRUE, revoked_at = %s WHERE token_hash = %s AND is_revoked = FALSE",
        (datetime.utcnow(), token_hash),
    )
    revoked = cur.rowcount > 0
    conn.commit()
    cur.close()

    if revoked:
        print(f"JWT: Refresh token revoked")
    else:
        print(f"JWT: Refresh token not found or already revoked")

    return revoked


def revoke_all_user_tokens(user_id, conn):
    """Revoke ALL refresh tokens for a user (logout all devices).

    Returns the number of tokens revoked.
    """
    cur = conn.cursor()
    cur.execute(
        "UPDATE refresh_tokens SET is_revoked = TRUE, revoked_at = %s WHERE user_id = %s AND is_revoked = FALSE",
        (datetime.utcnow(), user_id),
    )
    count = cur.rowcount
    conn.commit()
    cur.close()

    print(f"JWT: All tokens revoked for user {user_id} — {count} token(s) invalidated")
    return count


# =============================================================================
# CLEANUP — Remove expired/revoked tokens older than retention period
# =============================================================================

def cleanup_expired_tokens(conn):
    """Delete expired or revoked refresh tokens older than 30 days.

    Safe to call periodically (idempotent).
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM refresh_tokens WHERE (expires_at < %s) OR (is_revoked = TRUE AND revoked_at < %s)",
            (cutoff, cutoff),
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()

        if deleted > 0:
            print(f"JWT: Cleanup — removed {deleted} expired/revoked tokens")
    except Exception as e:
        print(f"JWT: Cleanup warning — {e}")


# =============================================================================
# DECORATOR — JWT-required endpoint protection (for future API use)
# =============================================================================

def jwt_required(f):
    """Decorator to protect API endpoints with JWT authentication.

    Checks for a valid JWT access token in the Authorization header.
    Falls back to session authentication if no JWT is provided,
    maintaining backward compatibility with the existing session system.

    Usage:
        @app.route("/api/protected")
        @jwt_required
        def protected_route():
            # request.jwt_payload is available if JWT was used
            # session["user_id"] is available if session was used
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Try JWT first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_access_token(token)
            if payload:
                request.jwt_payload = payload
                return f(*args, **kwargs)
            else:
                return jsonify({"error": "Invalid or expired access token"}), 401

        # Fall back to session authentication
        if "user_id" in session:
            request.jwt_payload = None  # Mark as session-authenticated
            return f(*args, **kwargs)

        return jsonify({"error": "Authentication required", "login_required": True}), 401

    return decorated


# =============================================================================
# HELPER — Generate token pair for auth responses
# =============================================================================

def generate_token_pair(user_id, username, conn, device_info=None):
    """Generate both access and refresh tokens for a user.

    Convenience function used during login, signup, and OAuth flows.

    Returns dict with token fields to merge into auth responses.
    """
    access_token = create_access_token(user_id, username)
    refresh_token = create_refresh_token(user_id, conn, device_info)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRY_MINUTES * 60,
    }
