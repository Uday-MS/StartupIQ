# StartupIQ — AI Agent Development Memory

# Project Overview

StartupIQ is an AI-powered startup intelligence and analytics platform built using Flask, PostgreSQL, Machine Learning, and cloud deployment architecture.

The platform is evolving from a hackathon MVP into a production-grade SaaS ecosystem focused on:

* startup analytics
* funding intelligence
* AI-driven recommendations
* investor-founder ecosystem
* startup intelligence automation

The long-term vision is to build a continuously updating AI-powered startup intelligence platform with:

* investor matching
* founder profiles
* startup scoring
* automated data-refresh agents
* SaaS analytics
* premium subscription features

---

# Current Production Status

Deployment Status:

* Live on Render
* Production PostgreSQL connected
* Google OAuth working
* Session authentication active
* Frontend and backend stable

Current live deployment architecture:

* Flask backend
* Gunicorn production server
* PostgreSQL database
* Render hosting
* Environment variable configuration

---

# Current Tech Stack

## Backend

* Python
* Flask
* Gunicorn
* PostgreSQL
* SQLite fallback support
* Authlib
* REST APIs

## Frontend

* HTML
* CSS
* JavaScript

## Machine Learning

* Pandas
* NumPy
* Scikit-learn
* Joblib

## Authentication

* Session-based authentication
* Google OAuth via Authlib

## Deployment

* Render
* Environment variables
* Gunicorn startup architecture

---

# Current Working Features

## Authentication Features

* Signup/Login system
* Session authentication
* Google OAuth login via Authlib
* Password hashing
* Password validation policy
* Persistent sessions
* Environment variable security

## Password Policy

Passwords currently require:

* minimum 8 characters
* at least 1 uppercase letter
* at least 1 number
* at least 1 special character

## Database Features

* PostgreSQL production integration
* SQLite fallback support
* Connection pooling
* Dynamic DB initialization

## Startup Platform Features

* Startup analytics dashboard
* Funding trend analytics
* Country analysis
* Sector analysis
* Indian startup analytics
* Search functionality
* Recommendation engine
* Save startup functionality
* Personalized recommendations

## Machine Learning Features

* Startup funding prediction
* Encoders preprocessing
* Recommendation analytics

## Deployment Features

* Render deployment
* BASE_URL environment architecture
* Google OAuth redirect handling
* Gunicorn production startup
* Environment variable configuration

---

# Current Stable Architecture

The application architecture is currently stable.

DO NOT:

* rewrite architecture
* redesign backend
* redesign frontend unnecessarily
* refactor unrelated code
* rename working routes
* rewrite APIs
* break deployment configuration
* remove session authentication
* break Google OAuth
* redesign database structure unnecessarily

Maintain current working production architecture.

---

# Existing Authentication Architecture

Current authentication system:

* session-based authentication
* Flask session management
* Google OAuth via Authlib
* PostgreSQL user storage

Current session structure:

* session["user_id"]
* session["username"]

These MUST remain compatible.

---

# JWT + Refresh Token Architecture (Hybrid)

JWT authentication is layered alongside existing session authentication.
The website continues to use sessions. JWT is available for future API scalability.

## Architecture

* Hybrid model: Session (primary) + JWT (additive)
* Session authentication remains the primary auth mechanism
* JWT access tokens (15 min) + refresh tokens (30 days)
* Refresh tokens stored as SHA-256 hashes in `refresh_tokens` table
* Token rotation on every refresh (old token invalidated)
* Replay detection: reuse of revoked token triggers family revocation

## Key Files

* jwt_auth.py — JWT token creation, validation, rotation, revocation
* auth.py — JWT routes (/api/token/refresh, /api/token/revoke, /api/token/status)
* db.py — refresh_tokens table schema

## JWT API Routes

* POST /api/token/refresh — exchange refresh token for new pair
* POST /api/token/revoke — revoke refresh token (single or all)
* GET /api/token/status — retrieve JWT tokens from session (post-OAuth)

## Token Responses

Login, signup (verify-signup-otp), and Google OAuth responses include JWT tokens
alongside existing session fields. Frontend can ignore JWT fields — they are additive.

## Environment Variables

* JWT_SECRET_KEY (optional) — separate signing key for JWT
* Falls back to SECRET_KEY if JWT_SECRET_KEY is not set

## Security

* Access tokens: HS256 signed, 15-min expiry
* Refresh tokens: secrets.token_urlsafe(64), SHA-256 hashed in DB
* Token rotation invalidates previous refresh token
* Revoked token reuse triggers all-token revocation for that user
* Expired tokens cleaned up periodically

---

# RBAC + Founder/Investor Profiles Architecture

Profile-based RBAC system. Roles are determined by profile existence (not a fixed column).

## Architecture

* Users can optionally be: normal user, founder, investor, or both
* Roles determined by profile table existence (no enum, no role column)
* Separate PostgreSQL tables: `founder_profiles`, `investor_profiles`
* Linked via `user_id → users.id` (UNIQUE foreign key)
* Each user can have at most one founder profile and one investor profile

## Key Files

* profiles.py — Profile CRUD Blueprint + RBAC helper functions
* db.py — founder_profiles + investor_profiles table schemas
* templates/founder_profile.html — Founder profile page
* templates/investor_profile.html — Investor profile page

## API Routes

* GET/POST/PUT/DELETE /profile/founder — Founder profile CRUD
* GET/POST/PUT/DELETE /profile/investor — Investor profile CRUD
* GET /profile/roles — Current user's roles (based on profile existence)
* GET /founder-profile — Render founder profile page
* GET /investor-profile — Render investor profile page

## Template Context

The `inject_user()` context processor provides:
* `current_user.has_founder_profile` — boolean
* `current_user.has_investor_profile` — boolean

These are used in the navbar dropdown to show dynamic labels.

## Security

* All profile routes require `session["user_id"]`
* Users can only access/modify their own profiles
* Ownership validated via user_id WHERE clause
* Protected routes: /founder-profile, /investor-profile

---

# Existing Environment Variables

Current environment variables include:

* SECRET_KEY
* DATABASE_URL
* GOOGLE_CLIENT_ID
* GOOGLE_CLIENT_SECRET
* EMAIL_USER
* EMAIL_PASS
* BASE_URL

Do not redesign environment architecture unnecessarily.

---

# Current Known Issues

## SMTP / Email Delivery — RESOLVED

Gmail SMTP was replaced with Resend API (email_service.py) for reliable cloud email delivery.

Current email architecture:

* Resend API via official Python SDK
* email_service.py handles all transactional email
* Professional HTML email templates
* Sender: StartupIQ \<onboarding@resend.dev\> (Resend default)
* No SMTP dependencies
* Railway/Render compatible
* Environment variable: RESEND_API_KEY

Email types supported:

* OTP verification emails
* Password reset emails
* Email verification emails

## Security Improvements Pending

* JWT authentication
* Refresh tokens
* CSRF protection
* Rate limiting
* OTP verification
* Brute-force prevention

---

# Development Rules For Future AI Agents

Future AI agents MUST:

## Required Rules

* continue incrementally
* preserve production compatibility
* generate minimal safe changes
* preserve frontend behavior
* preserve APIs
* preserve session auth compatibility
* preserve PostgreSQL compatibility
* preserve Google OAuth compatibility
* preserve deployment architecture

## Forbidden Actions

DO NOT:

* regenerate entire application
* rewrite unrelated files
* redesign architecture
* break working routes
* break current frontend
* remove stable features
* convert entire auth system unexpectedly
* rewrite database layer unnecessarily

---

# Current Project Roadmap

# Phase 3 — Authentication & Security

## Planned Features

* Unified Email OTP Verification
* Email verification before account creation
* JWT authentication
* Refresh token architecture
* OTP resend system
* OTP expiry handling
* Brute-force prevention
* Secure token validation
* CSRF protection
* Rate limiting

Target signup flow:
Signup
→ Send OTP
→ Verify OTP
→ Create Account
→ Create Session

---

# Phase 4 — SaaS Ecosystem Features

## Investor Matching

AI-based investor recommendation system matching:

* startup domain
* funding stage
* geography
* investor interests

## Founder Profiles

Professional founder identity system:

* startup portfolio
* funding details
* startup analytics
* traction
* AI scoring

## Startup Scoring

AI-generated startup quality/intelligence scoring system.

## Referral System

* referral codes
* invite tracking
* referral analytics

## Premium SaaS Features

* advanced analytics
* premium dashboards
* investor insights
* startup intelligence subscriptions

---

# Phase 5 — AI Startup Intelligence Agent

Planned AI data agent responsibilities:

* fetch startup ecosystem data automatically
* update startup database monthly
* refresh analytics automatically
* track startup ecosystem changes
* process startup intelligence data
* automate data ingestion pipeline

Potential future sources:

* Crunchbase
* Product Hunt
* YC ecosystem
* startup APIs
* startup news sources

Goal:
Transform StartupIQ into a live startup intelligence platform instead of a static analytics website.

---

# Security Standards

All future systems should maintain:

* hashed passwords
* secure tokens
* environment variable security
* OTP expiry
* token invalidation
* brute-force prevention
* secure session handling
* production-safe authentication flows

---

# Deployment Architecture

Current deployment:

* Render
* PostgreSQL
* Gunicorn
* Flask production app

Current startup command:
gunicorn app:app

BASE_URL must always match:

* Render deployment URL
* Google OAuth callback URL
* frontend deployment URL

---

# Final AI Development Instruction

StartupIQ is now a production-grade evolving SaaS platform.

Future AI agents should:

* extend safely
* improve incrementally
* avoid unnecessary rewrites
* maintain production stability
* maintain deployment compatibility
* preserve existing architecture
* prioritize minimal targeted changes only
