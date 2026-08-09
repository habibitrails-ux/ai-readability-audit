import os
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key-change-me")

# In-memory user database for tracking credits/subscriptions (Use a database in production)
USERS_DB = {}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Create user if they don't exist (3 free credits by default)
    if email not in USERS_DB:
        USERS_DB[email] = {"credits": 3, "is_pro": False}

    session["user_email"] = email
    user = USERS_DB[email]

    return jsonify(
        {"success": True, "credits": user["credits"], "is_pro": user["is_pro"]}
    )


@app.route("/audit", methods=["POST"])
def audit():
    user_email = session.get("user_email")

    if not user_email or user_email not in USERS_DB:
        return jsonify({"error": "Authentication required"}), 401

    user = USERS_DB[user_email]

    # Check credit limit for free users
    if not user["is_pro"] and user["credits"] <= 0:
        return jsonify({"error": "Credit limit reached"}), 429

    data = request.get_json() or {}
    target_url = data.get("url", "").strip()

    if not target_url:
        return jsonify({"error": "URL is required"}), 400

    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    parsed_url = urlparse(target_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    try:
        headers = {"User-Agent": "Mozilla/5.0 (AI-Readability-Bot/1.0)"}
        response = requests.get(target_url, headers=headers, timeout=10)
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Bot Accessibility / Robots.txt Check
        bot_score = 25
        try:
            robots_res = requests.get(f"{base_url}/robots.txt", timeout=5)
            if (
                robots_res.status_code == 200
                and "Disallow: /" in robots_res.text
            ):
                bot_score = 10
        except Exception:
            bot_score = 15

        # 2. Sitemap Check
        sitemap_score = 0
        try:
            sitemap_res = requests.get(f"{base_url}/sitemap.xml", timeout=5)
            if sitemap_res.status_code == 200:
                sitemap_score = 25
        except Exception:
            sitemap_score = 0

        # 3. Schema JSON-LD Check
        schema_scripts = soup.find_all(
            "script", type="application/ld+json"
        )
        json_ld_score = 25 if len(schema_scripts) > 0 else 0

        # 4. Semantic HTML Check
        semantic_tags = soup.find_all(
            ["header", "main", "footer", "article", "section", "nav"]
        )
        semantic_score = 25 if len(semantic_tags) >= 3 else 10

        overall_score = (
            bot_score + sitemap_score + json_ld_score + semantic_score
        )

        # Deduct credit if not pro
        if not user["is_pro"]:
            user["credits"] -= 1

        summary = (
            f"Audit completed for {parsed_url.netloc}. Found {len(schema_scripts)} JSON-LD blocks "
            f"and {len(semantic_tags)} semantic HTML elements."
        )

        return jsonify(
            {
                "overall_ai_score": overall_score,
                "summary": summary,
                "breakdown": {
                    "bot_accessibility": {"score": bot_score},
                    "sitemap_status": {"score": sitemap_score},
                    "schema_json_ld": {"score": json_ld_score},
                    "semantic_html": {"score": semantic_score},
                },
                "remaining_credits": user["credits"],
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to fetch site: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
