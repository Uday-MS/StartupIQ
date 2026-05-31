# =============================================================================
# PROFILES MODULE — Founder & Investor Profile CRUD + RBAC
# Handles: Profile creation, editing, viewing, deletion, role detection
# =============================================================================
import os
from datetime import datetime

from flask import Blueprint, request, jsonify, session, render_template

from db import get_conn, put_conn

profiles_bp = Blueprint("profiles", __name__)


# =============================================================================
# RBAC HELPER — Determine user roles from profile existence
# =============================================================================

def get_user_roles(user_id, conn):
    """Determine roles based on profile existence.

    Returns a list of role strings, e.g. ["user", "founder", "investor"].
    Every authenticated user has the "user" role.
    """
    roles = ["user"]

    cur = conn.cursor()
    cur.execute("SELECT id FROM founder_profiles WHERE user_id = %s", (user_id,))
    if cur.fetchone():
        roles.append("founder")

    cur.execute("SELECT id FROM investor_profiles WHERE user_id = %s", (user_id,))
    if cur.fetchone():
        roles.append("investor")

    cur.close()
    return roles


def _require_login():
    """Return error response if user is not logged in, else None."""
    if "user_id" not in session:
        return jsonify({"error": "Login required", "login_required": True}), 401
    return None


# =============================================================================
# FOUNDER PROFILE — CRUD API
# =============================================================================

# Founder profile field definitions (for safe extraction)
_FOUNDER_FIELDS = [
    "startup_name", "industry", "funding_stage", "website", "location",
    "problem_statement", "solution", "team_size", "funding_needed",
    "pitch_deck_url", "logo_url", "bio",
]


def _extract_founder_data(data):
    """Extract and sanitize founder profile fields from request data."""
    result = {}
    for field in _FOUNDER_FIELDS:
        val = data.get(field)
        if val is not None:
            if field == "team_size":
                try:
                    result[field] = max(1, int(val))
                except (ValueError, TypeError):
                    result[field] = 1
            elif field == "funding_needed":
                try:
                    result[field] = max(0, float(val))
                except (ValueError, TypeError):
                    result[field] = 0.0
            else:
                result[field] = str(val).strip()
    return result


def _row_to_founder_dict(row):
    """Convert a founder_profiles DB row to a dict."""
    return {
        "id": row[0],
        "user_id": row[1],
        "startup_name": row[2] or "",
        "industry": row[3] or "",
        "funding_stage": row[4] or "",
        "website": row[5] or "",
        "location": row[6] or "",
        "problem_statement": row[7] or "",
        "solution": row[8] or "",
        "team_size": row[9] or 1,
        "funding_needed": row[10] or 0,
        "pitch_deck_url": row[11] or "",
        "logo_url": row[12] or "",
        "bio": row[13] or "",
        "created_at": row[14].isoformat() if row[14] else None,
        "updated_at": row[15].isoformat() if row[15] else None,
    }


# ---------------------------------------------------------------------------
# GET /profile/founder — Get current user's founder profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/founder", methods=["GET"])
def get_founder_profile():
    """Return the logged-in user's founder profile as JSON."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    user_id = session["user_id"]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, user_id, startup_name, industry, funding_stage, website,
                      location, problem_statement, solution, team_size, funding_needed,
                      pitch_deck_url, logo_url, bio, created_at, updated_at
               FROM founder_profiles WHERE user_id = %s""",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()

        if not row:
            return jsonify({"exists": False, "profile": None})

        return jsonify({"exists": True, "profile": _row_to_founder_dict(row)})

    except Exception as e:
        print(f"❌ Get founder profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# POST /profile/founder — Create founder profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/founder", methods=["POST"])
def create_founder_profile():
    """Create a founder profile for the logged-in user."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    startup_name = (data.get("startup_name") or "").strip()
    if not startup_name:
        return jsonify({"error": "Startup name is required"}), 400

    user_id = session["user_id"]
    fields = _extract_founder_data(data)

    conn = get_conn()
    try:
        cur = conn.cursor()

        # Check if profile already exists
        cur.execute("SELECT id FROM founder_profiles WHERE user_id = %s", (user_id,))
        if cur.fetchone():
            cur.close()
            return jsonify({"error": "Founder profile already exists. Use PUT to update."}), 409

        now = datetime.utcnow()
        cur.execute(
            """INSERT INTO founder_profiles
               (user_id, startup_name, industry, funding_stage, website, location,
                problem_statement, solution, team_size, funding_needed,
                pitch_deck_url, logo_url, bio, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                user_id,
                fields.get("startup_name", startup_name),
                fields.get("industry", ""),
                fields.get("funding_stage", ""),
                fields.get("website", ""),
                fields.get("location", ""),
                fields.get("problem_statement", ""),
                fields.get("solution", ""),
                fields.get("team_size", 1),
                fields.get("funding_needed", 0),
                fields.get("pitch_deck_url", ""),
                fields.get("logo_url", ""),
                fields.get("bio", ""),
                now,
                now,
            ),
        )
        profile_id = cur.fetchone()[0]
        conn.commit()
        cur.close()

        print(f"Profiles: ✅ Founder profile created for user {user_id} (ID: {profile_id})")
        return jsonify({
            "success": True,
            "message": "Founder profile created successfully!",
            "profile_id": profile_id,
        }), 201

    except Exception as e:
        conn.rollback()
        print(f"❌ Create founder profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# PUT /profile/founder — Update founder profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/founder", methods=["PUT"])
def update_founder_profile():
    """Update the logged-in user's founder profile."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    user_id = session["user_id"]
    fields = _extract_founder_data(data)

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    # Ensure startup_name is not empty if provided
    if "startup_name" in fields and not fields["startup_name"]:
        return jsonify({"error": "Startup name cannot be empty"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()

        # Verify profile exists and belongs to user
        cur.execute("SELECT id FROM founder_profiles WHERE user_id = %s", (user_id,))
        if not cur.fetchone():
            cur.close()
            return jsonify({"error": "No founder profile found. Create one first."}), 404

        # Build dynamic UPDATE
        fields["updated_at"] = datetime.utcnow()
        set_clauses = ", ".join(f"{k} = %s" for k in fields.keys())
        values = list(fields.values()) + [user_id]

        cur.execute(
            f"UPDATE founder_profiles SET {set_clauses} WHERE user_id = %s",
            values,
        )
        conn.commit()
        cur.close()

        print(f"Profiles: ✅ Founder profile updated for user {user_id}")
        return jsonify({"success": True, "message": "Founder profile updated!"})

    except Exception as e:
        conn.rollback()
        print(f"❌ Update founder profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# DELETE /profile/founder — Delete founder profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/founder", methods=["DELETE"])
def delete_founder_profile():
    """Delete the logged-in user's founder profile."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    user_id = session["user_id"]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM founder_profiles WHERE user_id = %s", (user_id,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()

        if deleted == 0:
            return jsonify({"error": "No founder profile to delete"}), 404

        print(f"Profiles: ✅ Founder profile deleted for user {user_id}")
        return jsonify({"success": True, "message": "Founder profile deleted."})

    except Exception as e:
        conn.rollback()
        print(f"❌ Delete founder profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# INVESTOR PROFILE — CRUD API
# =============================================================================

_INVESTOR_FIELDS = [
    "fund_name", "investor_type", "investment_min", "investment_max",
    "preferred_industries", "preferred_stages", "preferred_locations",
    "website", "linkedin_url", "bio",
]


def _extract_investor_data(data):
    """Extract and sanitize investor profile fields from request data."""
    result = {}
    for field in _INVESTOR_FIELDS:
        val = data.get(field)
        if val is not None:
            if field in ("investment_min", "investment_max"):
                try:
                    result[field] = max(0, float(val))
                except (ValueError, TypeError):
                    result[field] = 0.0
            else:
                result[field] = str(val).strip()
    return result


def _row_to_investor_dict(row):
    """Convert an investor_profiles DB row to a dict."""
    return {
        "id": row[0],
        "user_id": row[1],
        "fund_name": row[2] or "",
        "investor_type": row[3] or "",
        "investment_min": row[4] or 0,
        "investment_max": row[5] or 0,
        "preferred_industries": row[6] or "",
        "preferred_stages": row[7] or "",
        "preferred_locations": row[8] or "",
        "website": row[9] or "",
        "linkedin_url": row[10] or "",
        "bio": row[11] or "",
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
    }


# ---------------------------------------------------------------------------
# GET /profile/investor — Get current user's investor profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/investor", methods=["GET"])
def get_investor_profile():
    """Return the logged-in user's investor profile as JSON."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    user_id = session["user_id"]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, user_id, fund_name, investor_type, investment_min,
                      investment_max, preferred_industries, preferred_stages,
                      preferred_locations, website, linkedin_url, bio,
                      created_at, updated_at
               FROM investor_profiles WHERE user_id = %s""",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()

        if not row:
            return jsonify({"exists": False, "profile": None})

        return jsonify({"exists": True, "profile": _row_to_investor_dict(row)})

    except Exception as e:
        print(f"❌ Get investor profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# POST /profile/investor — Create investor profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/investor", methods=["POST"])
def create_investor_profile():
    """Create an investor profile for the logged-in user."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    fund_name = (data.get("fund_name") or "").strip()
    if not fund_name:
        return jsonify({"error": "Fund/firm name is required"}), 400

    user_id = session["user_id"]
    fields = _extract_investor_data(data)

    conn = get_conn()
    try:
        cur = conn.cursor()

        # Check if profile already exists
        cur.execute("SELECT id FROM investor_profiles WHERE user_id = %s", (user_id,))
        if cur.fetchone():
            cur.close()
            return jsonify({"error": "Investor profile already exists. Use PUT to update."}), 409

        now = datetime.utcnow()
        cur.execute(
            """INSERT INTO investor_profiles
               (user_id, fund_name, investor_type, investment_min, investment_max,
                preferred_industries, preferred_stages, preferred_locations,
                website, linkedin_url, bio, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                user_id,
                fields.get("fund_name", fund_name),
                fields.get("investor_type", ""),
                fields.get("investment_min", 0),
                fields.get("investment_max", 0),
                fields.get("preferred_industries", ""),
                fields.get("preferred_stages", ""),
                fields.get("preferred_locations", ""),
                fields.get("website", ""),
                fields.get("linkedin_url", ""),
                fields.get("bio", ""),
                now,
                now,
            ),
        )
        profile_id = cur.fetchone()[0]
        conn.commit()
        cur.close()

        print(f"Profiles: ✅ Investor profile created for user {user_id} (ID: {profile_id})")
        return jsonify({
            "success": True,
            "message": "Investor profile created successfully!",
            "profile_id": profile_id,
        }), 201

    except Exception as e:
        conn.rollback()
        print(f"❌ Create investor profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# PUT /profile/investor — Update investor profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/investor", methods=["PUT"])
def update_investor_profile():
    """Update the logged-in user's investor profile."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    user_id = session["user_id"]
    fields = _extract_investor_data(data)

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    if "fund_name" in fields and not fields["fund_name"]:
        return jsonify({"error": "Fund/firm name cannot be empty"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute("SELECT id FROM investor_profiles WHERE user_id = %s", (user_id,))
        if not cur.fetchone():
            cur.close()
            return jsonify({"error": "No investor profile found. Create one first."}), 404

        fields["updated_at"] = datetime.utcnow()
        set_clauses = ", ".join(f"{k} = %s" for k in fields.keys())
        values = list(fields.values()) + [user_id]

        cur.execute(
            f"UPDATE investor_profiles SET {set_clauses} WHERE user_id = %s",
            values,
        )
        conn.commit()
        cur.close()

        print(f"Profiles: ✅ Investor profile updated for user {user_id}")
        return jsonify({"success": True, "message": "Investor profile updated!"})

    except Exception as e:
        conn.rollback()
        print(f"❌ Update investor profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# DELETE /profile/investor — Delete investor profile
# ---------------------------------------------------------------------------
@profiles_bp.route("/profile/investor", methods=["DELETE"])
def delete_investor_profile():
    """Delete the logged-in user's investor profile."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    user_id = session["user_id"]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM investor_profiles WHERE user_id = %s", (user_id,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()

        if deleted == 0:
            return jsonify({"error": "No investor profile to delete"}), 404

        print(f"Profiles: ✅ Investor profile deleted for user {user_id}")
        return jsonify({"success": True, "message": "Investor profile deleted."})

    except Exception as e:
        conn.rollback()
        print(f"❌ Delete investor profile error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# ROLES API — Check current user's roles
# =============================================================================

@profiles_bp.route("/profile/roles", methods=["GET"])
def get_roles():
    """Return the current user's roles based on profile existence."""
    auth_err = _require_login()
    if auth_err:
        return auth_err

    user_id = session["user_id"]
    conn = get_conn()
    try:
        roles = get_user_roles(user_id, conn)
        return jsonify({
            "user_id": user_id,
            "roles": roles,
            "is_founder": "founder" in roles,
            "is_investor": "investor" in roles,
        })
    except Exception as e:
        print(f"❌ Get roles error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)


# =============================================================================
# PROFILE PAGE ROUTES — Render HTML templates
# =============================================================================

@profiles_bp.route("/founder-profile")
def founder_profile_page():
    """Render the founder profile page."""
    if "user_id" not in session:
        return jsonify({"error": "Login required", "login_required": True}), 401

    return render_template("founder_profile.html", page="founder-profile")


@profiles_bp.route("/investor-profile")
def investor_profile_page():
    """Render the investor profile page."""
    if "user_id" not in session:
        return jsonify({"error": "Login required", "login_required": True}), 401

    return render_template("investor_profile.html", page="investor-profile")
