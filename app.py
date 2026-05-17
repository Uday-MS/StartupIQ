from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import pandas as pd
import numpy as np
import joblib
import os
from dotenv import load_dotenv
from functools import wraps

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
DATABASE_URL = os.getenv("DATABASE_URL")

SECRET_KEY = os.getenv("SECRET_KEY")


app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


# =============================================================================
# DATABASE INIT — Create tables on startup
# =============================================================================
from db import init_db
init_db()

# =============================================================================
# AUTH BLUEPRINT — Register auth routes (/signup, /login, /logout, etc.)
# =============================================================================
from auth import auth_bp
app.register_blueprint(auth_bp)


# =============================================================================
# ROUTE PROTECTION — Require login for certain pages
# =============================================================================
PROTECTED_ROUTES = {"/india", "/search", "/predict"}


@app.before_request
def check_auth():
    """Block protected routes for unauthenticated users."""
    if request.path in PROTECTED_ROUTES and "user_id" not in session:
        # For AJAX/fetch requests, return JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Login required", "login_required": True}), 401
        # For normal page loads, redirect to home with login trigger
        return redirect("/?login_required=1")


# =============================================================================
# TEMPLATE CONTEXT — Inject user info into all templates
# =============================================================================
@app.context_processor
def inject_user():
    """Make current user available in all templates."""
    return {
        "current_user": {
            "logged_in": "user_id" in session,
            "username": session.get("username", ""),
            "user_id": session.get("user_id"),
        }
    }

# =============================================================================
# DATA LOADING — Global dataset
# =============================================================================
df = pd.read_csv("cleaned_data.csv")

# =============================================================================
# ML MODEL LOADING — Load once at startup (cached)
# =============================================================================
_model = None
_encoders_payload = None


def get_model():
    """Load and cache the trained ML model + encoders."""
    global _model, _encoders_payload
    if _model is None:
        model_path = os.path.join(os.path.dirname(__file__), "model.pkl")
        enc_path = os.path.join(os.path.dirname(__file__), "encoders.pkl")
        if os.path.exists(model_path) and os.path.exists(enc_path):
            _model = joblib.load(model_path)
            _encoders_payload = joblib.load(enc_path)
            
        else:
            print("⚠️  model.pkl / encoders.pkl not found — run model.py first")
    return _model, _encoders_payload


# Eagerly load model at startup
get_model()

# =============================================================================
# DATA LOADING — Indian startups dataset
# =============================================================================
def load_indian_data():
    """Load and clean the Indian startups CSV."""
    idf = pd.read_csv("indian_startups.csv", encoding="utf-8-sig")

    # Parse amounts: strip commas and convert to float
    def parse_amount(x):
        try:
            return float(str(x).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    idf["Amount_USD"] = idf["Amount in USD"].apply(parse_amount)

    # Extract year from date column (dd/mm/yyyy format)
    idf["Date_Parsed"] = pd.to_datetime(
        idf["Date dd/mm/yyyy"], format="%d/%m/%Y", errors="coerce"
    )
    idf["Year"] = idf["Date_Parsed"].dt.year

    # Clean industry names — group similar ones
    industry_map = {
        "eCommerce": "E-Commerce",
        "ECommerce": "E-Commerce",
        "E-commerce": "E-Commerce",
        "Consumer Internet": "Consumer Internet",
        "Technology": "Technology",
        "Healthcare": "Healthcare",
        "Finance": "Finance",
        "FinTech": "FinTech",
        "Logistics": "Logistics",
        "Education": "Education",
        "E-Tech": "EdTech",
        "Ed-Tech": "EdTech",
    }
    idf["Industry_Clean"] = idf["Industry Vertical"].map(industry_map).fillna(idf["Industry Vertical"])

    return idf

indian_df = load_indian_data()


# =============================================================================
# PAGE ROUTES — Existing (enhanced) + New
# =============================================================================

@app.route("/")
def home():
    """Dashboard home page with KPIs, charts data, and top startups."""
    # Original KPIs (preserved)
    total_funding = df["Amount Raised (USD)"].sum()
    total_funding_b = round(total_funding / 1e9, 2)
    total_startups = df["Startup Name"].nunique()
    top_country = df.groupby("Country")["Amount Raised (USD)"].sum().idxmax()

    # Additional KPIs
    avg_funding = round(df["Amount Raised (USD)"].mean() / 1e6, 2)  # in millions
    total_countries = df["Country"].nunique()

    # Mini trend data (for home page chart)
    yearly = df.groupby("Year")["Amount Raised (USD)"].sum()
    if 2026 in yearly.index:
        yearly = yearly.drop(2026)
    trend_years = yearly.index.tolist()
    trend_funding = yearly.values.tolist()

    # Sector distribution (for doughnut chart)
    sector_dist = df.groupby("Industry")["Amount Raised (USD)"].sum().sort_values(ascending=False)
    sector_labels = sector_dist.index.tolist()
    sector_values = sector_dist.values.tolist()

    # Top 10 startups by funding
    top_startups = (
        df.sort_values("Amount Raised (USD)", ascending=False)
        .head(10)[["Startup Name", "Industry", "Country", "Funding Stage", "Amount Raised (USD)"]]
        .to_dict("records")
    )

    # --- Data for scroll-based sections ---

    # Explore section: funding trends (same as /trends route)
    explore_years = trend_years
    explore_funding = trend_funding
    countries = sorted(df["Country"].unique().tolist())

    # Sector Analysis section (same as /sector route)
    sector_bar_data = df.groupby("Industry")["Amount Raised (USD)"].sum().sort_values(ascending=False)
    sector_bar_labels = sector_bar_data.index.tolist()
    sector_bar_values = sector_bar_data.values.tolist()

    # Country Analysis section (same as /country route)
    country_bar_data = (
        df.groupby("Country")["Amount Raised (USD)"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
    country_bar_labels = country_bar_data.index.tolist()
    country_bar_values = country_bar_data.values.tolist()
    industries = sorted(df["Industry"].unique().tolist())

    return render_template(
        "index.html",
        page="dashboard",
        total_funding=total_funding_b,
        total_startups=total_startups,
        top_country=top_country,
        avg_funding=avg_funding,
        total_countries=total_countries,
        trend_years=trend_years,
        trend_funding=trend_funding,
        sector_labels=sector_labels,
        sector_values=sector_values,
        top_startups=top_startups,
        # Scroll-based section data
        explore_years=explore_years,
        explore_funding=explore_funding,
        countries=countries,
        sector_bar_labels=sector_bar_labels,
        sector_bar_values=sector_bar_values,
        country_bar_labels=country_bar_labels,
        country_bar_values=country_bar_values,
        industries=industries,
    )


@app.route("/predict")
def predict():
    countries = sorted(df["Country"].unique().tolist())
    industries = sorted(df["Industry"].unique().tolist())
    stages = sorted(df["Funding Stage"].unique().tolist())
    return render_template(
        "predict.html",
        page="predict",
        countries=countries,
        industries=industries,
        stages=stages,
    )


@app.route("/trends")
def trends():
    """Funding trends page with year-wise line chart."""
    df_copy = df.copy()
    yearly = df_copy.groupby("Year")["Amount Raised (USD)"].sum()
    if 2026 in yearly.index:
        yearly = yearly.drop(2026)

    years = yearly.index.tolist()
    funding = yearly.values.tolist()

    # Filter options
    countries = sorted(df["Country"].unique().tolist())
    all_years = sorted(df["Year"].unique().tolist())
    if 2026 in all_years:
        all_years.remove(2026)

    return render_template(
        "trends.html",
        page="trends",
        years=years,
        funding=funding,
        countries=countries,
        all_years=all_years,
    )


@app.route("/sector")
def sector():
    """Sector analysis page with bar chart."""
    sector_data = df.groupby("Industry")["Amount Raised (USD)"].sum().sort_values(ascending=False)

    labels = sector_data.index.tolist()
    values = sector_data.values.tolist()

    # Filter options
    countries = sorted(df["Country"].unique().tolist())

    return render_template(
        "sector.html",
        page="sectors",
        labels=labels,
        values=values,
        countries=countries,
    )


@app.route("/country")
def country():
    """Country analysis page with bar chart."""
    country_data = (
        df.groupby("Country")["Amount Raised (USD)"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    labels = country_data.index.tolist()
    values = country_data.values.tolist()

    # Filter options
    industries = sorted(df["Industry"].unique().tolist())

    return render_template(
        "country.html",
        page="countries",
        labels=labels,
        values=values,
        industries=industries,
    )


@app.route("/india")
def india():
    """India analysis page with Indian startup data."""
    idf = indian_df

    # KPIs
    total_indian_funding = idf["Amount_USD"].sum()
    total_indian_funding_m = round(total_indian_funding / 1e6, 2)
    total_indian_startups = idf["Startup Name"].nunique()
    top_city = idf.groupby("City  Location")["Amount_USD"].sum().idxmax()
    top_sector = idf.groupby("Industry_Clean")["Amount_USD"].sum().idxmax()

    # Year-wise Indian funding
    india_yearly = idf.groupby("Year")["Amount_USD"].sum().sort_index()
    india_years = [int(y) for y in india_yearly.index.dropna().tolist()]
    india_funding = india_yearly.values.tolist()

    # Top 10 Indian sectors
    india_sectors = idf.groupby("Industry_Clean")["Amount_USD"].sum().sort_values(ascending=False).head(10)
    india_sector_labels = india_sectors.index.tolist()
    india_sector_values = india_sectors.values.tolist()

    # Global vs India comparison — align years
    global_yearly = df.groupby("Year")["Amount Raised (USD)"].sum()
    if 2026 in global_yearly.index:
        global_yearly = global_yearly.drop(2026)

    # Find overlapping years
    common_years = sorted(set(global_yearly.index.astype(int)) & set(india_yearly.index.dropna().astype(int)))
    compare_years = [int(y) for y in common_years]
    compare_global = [float(global_yearly.get(y, 0)) for y in common_years]
    compare_india = [float(india_yearly.get(y, 0)) for y in common_years]

    return render_template(
        "india.html",
        page="india",
        total_indian_funding=total_indian_funding_m,
        total_indian_startups=total_indian_startups,
        top_city=top_city,
        top_sector=top_sector,
        india_years=india_years,
        india_funding=india_funding,
        india_sector_labels=india_sector_labels,
        india_sector_values=india_sector_values,
        compare_years=compare_years,
        compare_global=compare_global,
        compare_india=compare_india,
    )


@app.route("/search")
def search_page():
    """Search page — renders the search UI."""
    return render_template("search.html", page="search")


# =============================================================================
# API ROUTES — JSON endpoints for dynamic frontend updates
# =============================================================================

@app.route("/api/trends")
def api_trends():
    """Filtered funding trends. Query params: country, year."""
    filtered = df.copy()
    country_filter = request.args.get("country", "all")
    if country_filter != "all":
        filtered = filtered[filtered["Country"] == country_filter]

    yearly = filtered.groupby("Year")["Amount Raised (USD)"].sum()
    if 2026 in yearly.index:
        yearly = yearly.drop(2026)

    return jsonify({
        "years": yearly.index.tolist(),
        "funding": yearly.values.tolist(),
    })


@app.route("/api/sectors")
def api_sectors():
    """Filtered sector data. Query params: country."""
    filtered = df.copy()
    country_filter = request.args.get("country", "all")
    if country_filter != "all":
        filtered = filtered[filtered["Country"] == country_filter]

    sector_data = (
        filtered.groupby("Industry")["Amount Raised (USD)"]
        .sum()
        .sort_values(ascending=False)
    )

    return jsonify({
        "labels": sector_data.index.tolist(),
        "values": sector_data.values.tolist(),
    })


@app.route("/api/countries")
def api_countries():
    """Filtered country data. Query params: industry."""
    filtered = df.copy()
    industry_filter = request.args.get("industry", "all")
    if industry_filter != "all":
        filtered = filtered[filtered["Industry"] == industry_filter]

    country_data = (
        filtered.groupby("Country")["Amount Raised (USD)"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    return jsonify({
        "labels": country_data.index.tolist(),
        "values": country_data.values.tolist(),
    })


@app.route("/api/search")
def api_search():
    """Search startups by name (partial, case-insensitive). Query param: name."""
    query = request.args.get("name", "").strip()
    if not query:
        return jsonify({"results": []})

    # Search in global dataset
    mask = df["Startup Name"].str.contains(query, case=False, na=False)
    results = (
        df[mask]
        .head(20)[["Startup Name", "Industry", "Country", "Funding Stage", "Amount Raised (USD)"]]
        .to_dict("records")
    )

    # Also search in Indian dataset
    mask_india = indian_df["Startup Name"].str.contains(query, case=False, na=False)
    india_results = indian_df[mask_india].head(10)
    for _, row in india_results.iterrows():
        results.append({
            "Startup Name": row["Startup Name"],
            "Industry": row["Industry_Clean"],
            "Country": "India",
            "Funding Stage": row.get("InvestmentnType", "N/A"),
            "Amount Raised (USD)": row["Amount_USD"],
        })

    # Deduplicate by name (keep first occurrence)
    seen = set()
    unique_results = []
    for r in results:
        name = r["Startup Name"]
        if name not in seen:
            seen.add(name)
            unique_results.append(r)

    return jsonify({"results": unique_results[:20]})


@app.route("/api/top-startups")
def api_top_startups():
    """Top 10 startups by funding amount."""
    top = (
        df.sort_values("Amount Raised (USD)", ascending=False)
        .head(10)[["Startup Name", "Industry", "Country", "Funding Stage", "Amount Raised (USD)"]]
        .to_dict("records")
    )
    return jsonify({"startups": top})


@app.route("/api/india/trends")
def api_india_trends():
    """Indian startups year-wise funding trends."""
    yearly = indian_df.groupby("Year")["Amount_USD"].sum().sort_index()
    return jsonify({
        "years": [int(y) for y in yearly.index.dropna().tolist()],
        "funding": yearly.values.tolist(),
    })


@app.route("/api/india/sectors")
def api_india_sectors():
    """Top Indian sectors by funding."""
    sectors = (
        indian_df.groupby("Industry_Clean")["Amount_USD"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
    return jsonify({
        "labels": sectors.index.tolist(),
        "values": sectors.values.tolist(),
    })


@app.route("/api/comparison")
def api_comparison():
    """Global vs India year-wise funding comparison."""
    global_yearly = df.groupby("Year")["Amount Raised (USD)"].sum()
    if 2026 in global_yearly.index:
        global_yearly = global_yearly.drop(2026)

    india_yearly = indian_df.groupby("Year")["Amount_USD"].sum().sort_index()

    common_years = sorted(
        set(global_yearly.index.astype(int)) & set(india_yearly.index.dropna().astype(int))
    )

    return jsonify({
        "years": [int(y) for y in common_years],
        "global_funding": [float(global_yearly.get(y, 0)) for y in common_years],
        "india_funding": [float(india_yearly.get(y, 0)) for y in common_years],
    })


@app.route("/api/country-analytics")
def api_country_analytics():
    """Country-level analytics. Query param: name (country name)."""
    country_name = request.args.get("name", "").strip()
    if not country_name:
        return jsonify({"error": "Missing country name"}), 400

    # Filter data for the country
    filtered = df[df["Country"].str.lower() == country_name.lower()]

    if filtered.empty:
        return jsonify({"error": f"No data found for '{country_name}'"}), 404

    total_funding = float(filtered["Amount Raised (USD)"].sum())
    avg_funding = float(filtered["Amount Raised (USD)"].mean())
    num_startups = int(filtered["Startup Name"].nunique())

    # Sector-wise funding
    sector_data = (
        filtered.groupby("Industry")["Amount Raised (USD)"]
        .sum()
        .sort_values(ascending=False)
    )
    top_sector = sector_data.index[0] if len(sector_data) > 0 else "N/A"

    return jsonify({
        "country": country_name,
        "total_funding": total_funding,
        "avg_funding": avg_funding,
        "num_startups": num_startups,
        "top_sector": top_sector,
        "sector_labels": sector_data.index.tolist(),
        "sector_values": [float(v) for v in sector_data.values.tolist()],
    })


@app.route("/api/filters")
def api_filters():
    """Available filter options for dropdowns."""
    years = sorted(df["Year"].unique().tolist())
    if 2026 in years:
        years.remove(2026)

    return jsonify({
        "countries": sorted(df["Country"].unique().tolist()),
        "industries": sorted(df["Industry"].unique().tolist()),
        "years": years,
    })


# =============================================================================
# ML PREDICTION API
# =============================================================================

@app.route("/api/predict", methods=["POST"])
def api_predict():
    """Predict startup funding using the trained Random Forest model."""
    model, payload = get_model()

    if model is None or payload is None:
        return jsonify({"error": "ML model not loaded. Run model.py first."}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    country = data.get("country", "").strip()
    sector = data.get("sector", "").strip()
    stage = data.get("stage", "").strip()

    if not country or not sector or not stage:
        return jsonify({"error": "Missing required fields: country, sector, stage"}), 400

    encoders = payload["encoders"]
    feature_names = payload["feature_names"]
    max_funding = payload["max_funding"]
    percentile_90 = payload["percentile_90"]

    # Validate that inputs are known to the encoders
    errors = []
    if country not in encoders["Country"].classes_:
        errors.append(f"Unknown country: '{country}'")
    if sector not in encoders["Industry"].classes_:
        errors.append(f"Unknown sector: '{sector}'")
    if stage not in encoders["Funding Stage"].classes_:
        errors.append(f"Unknown funding stage: '{stage}'")

    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    # Encode inputs
    try:
        encoded_country = encoders["Country"].transform([country])[0]
        encoded_industry = encoders["Industry"].transform([sector])[0]
        encoded_stage = encoders["Funding Stage"].transform([stage])[0]
    except Exception as e:
        return jsonify({"error": f"Encoding failed: {str(e)}"}), 400

    # Predict
    X_input = pd.DataFrame(
        [[encoded_country, encoded_industry, encoded_stage]],
        columns=feature_names,
    )
    predicted_funding = float(model.predict(X_input)[0])

    # Ensure non-negative
    predicted_funding = max(0, predicted_funding)

    # Success probability: normalized against dataset distribution
    success_probability = min(95, max(50, (predicted_funding / percentile_90) * 75))
    success_probability = round(success_probability, 1)

    # Model metadata
    r2 = payload.get("r2_score", 0)
    mae = payload.get("mae", 0)

    return jsonify({
        "predicted_funding": round(predicted_funding, 2),
        "success_probability": success_probability,
        "model_r2": round(r2, 4),
        "model_mae": round(mae, 2),
    })


# =============================================================================
# RECOMMENDATION ENGINE — Pandas-powered recommendations
# =============================================================================

@app.route("/api/recommendations")
def api_recommendations():
    """
    Recommend startups based on user's saved startups.
    Gets saved industries/countries from auth module, filters main dataset.
    Falls back to top startups if no saved preferences exist.
    """
    if "user_id" not in session:
        return jsonify({"error": "Login required", "login_required": True}), 401

    from db import get_conn, put_conn

    user_id = session["user_id"]
    print(f"Generating recommendations for user: {user_id}")

    conn = get_conn()
    try:
        cur = conn.cursor()

        # Get user's saved startup preferences
        cur.execute(
            """SELECT DISTINCT industry, country FROM saved_startups
               WHERE user_id = %s AND (industry IS NOT NULL OR country IS NOT NULL)""",
            (user_id,),
        )
        saved_prefs = cur.fetchall()

        # Get names of already saved startups to exclude them
        cur.execute(
            "SELECT startup_name FROM saved_startups WHERE user_id = %s",
            (user_id,),
        )
        saved_names = {row[0] for row in cur.fetchall()}
        cur.close()

        if not saved_prefs:
            # Fallback: return top startups as recommendations
            print(f"No saved preferences for user {user_id} — returning fallback (top startups)")
            fallback = (
                df.sort_values("Amount Raised (USD)", ascending=False)
                .head(12)[["Startup Name", "Industry", "Country", "Funding Stage", "Amount Raised (USD)"]]
                .to_dict("records")
            )
            print(f"Recommendations generated: {len(fallback)} fallback startups")
            return jsonify({
                "recommendations": fallback,
                "message": "Top startups — save some to get personalized recommendations!",
            })

        industries = {r[0] for r in saved_prefs if r[0]}
        countries = {r[1] for r in saved_prefs if r[1]}
        print(f"User preferences — industries: {industries}, countries: {countries}")

        # Filter dataset for matching industry OR country
        mask = pd.Series([False] * len(df))
        if industries:
            mask = mask | df["Industry"].isin(industries)
        if countries:
            mask = mask | df["Country"].isin(countries)

        # Exclude already saved startups
        mask = mask & ~df["Startup Name"].isin(saved_names)

        recommendations = (
            df[mask]
            .sort_values("Amount Raised (USD)", ascending=False)
            .head(12)[["Startup Name", "Industry", "Country", "Funding Stage", "Amount Raised (USD)"]]
            .to_dict("records")
        )

        # If personalized results are too few, pad with top startups
        if len(recommendations) < 4:
            print(f"Only {len(recommendations)} personalized results — adding fallback top startups")
            existing_names = {r["Startup Name"] for r in recommendations} | saved_names
            fallback = (
                df[~df["Startup Name"].isin(existing_names)]
                .sort_values("Amount Raised (USD)", ascending=False)
                .head(12 - len(recommendations))[["Startup Name", "Industry", "Country", "Funding Stage", "Amount Raised (USD)"]]
                .to_dict("records")
            )
            recommendations.extend(fallback)

        print(f"Recommendations generated: {len(recommendations)} startups for user {user_id}")
        return jsonify({"recommendations": recommendations})

    except Exception as e:
        print(f"❌ Recommendations error for user {user_id}: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        put_conn(conn)




# =============================================================================
# RUN SERVER
# =============================================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))