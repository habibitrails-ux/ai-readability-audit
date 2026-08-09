import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "super-secret-key-12345")

# Basic in-memory fallback for development
USERS_DB = {}
OTP_DB = {}

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

def audit_url(target_url):
    """
    Audits a target URL across 4 main pillars:
    1. Bot Accessibility (robots.txt)
    2. Sitemap Status
    3. Schema JSON-LD
    4. Semantic HTML
    """
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    try:
        parsed_url = urllib.parse.urlparse(target_url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    except Exception:
        base_domain = target_url

    scores = {
        "bot_accessibility": 0,
        "sitemap_status": 0,
        "schema_json_ld": 0,
        "semantic_html": 0
    }

    headers = {"User-Agent": "Mozilla/5.0 (Compatible; AIReadabilityBot/1.0)"}

    # 1. Bot Accessibility
    try:
        robots_res = requests.get(f"{base_domain}/robots.txt", headers=headers, timeout=5)
        if robots_res.status_code == 200:
            if "Disallow: /" not in robots_res.text:
                scores["bot_accessibility"] = 25
            else:
                scores["bot_accessibility"] = 10
        else:
            scores["bot_accessibility"] = 15
    except Exception:
        scores["bot_accessibility"] = 10

    # 2. Sitemap Status
    try:
        sitemap_res = requests.get(f"{base_domain}/sitemap.xml", headers=headers, timeout=5)
        if sitemap_res.status_code == 200:
            scores["sitemap_status"] = 25
        else:
            scores["sitemap_status"] = 10
    except Exception:
        scores["sitemap_status"] = 0

    # 3 & 4. Parse DOM for Schemas and Semantic HTML
    try:
        res = requests.get(target_url, headers=headers, timeout=8)
        if res.status_code == 200 and res.text:
            soup = BeautifulSoup(res.text, "html.parser")

            # Schema JSON-LD
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            if json_ld_scripts:
                scores["schema_json_ld"] = 25 if len(json_ld_scripts) > 1 else 15
            else:
                scores["schema_json_ld"] = 0

            # Semantic Tags
            semantic_tags = ["header", "nav", "main", "article", "section", "footer", "aside"]
            found_tags = [tag for tag in semantic_tags if soup.find(tag)]
            if len(found_tags) >= 4:
                scores["semantic_html"] = 25
            elif len(found_tags) >= 2:
                scores["semantic_html"] = 15
            else:
                scores["semantic_html"] = 5
    except Exception:
        scores["schema_json_ld"] = 0
        scores["semantic_html"] = 0

    total_score = sum(scores.values())

    return {
        "url": target_url,
        "overall_score": total_score,
        "summary": f"Audit completed for {target_url}. Overall score is {total_score}/100.",
        "breakdown": scores
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/send-otp", methods=["POST", "OPTIONS"])
def send_otp():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    OTP_DB[email] = "123456"
    return jsonify({"message": "OTP sent successfully. Use code: 123456"}), 200


@app.route("/verify-otp", methods=["POST", "OPTIONS"])
def verify_otp():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    otp = data.get("otp", "").strip()

    # Allow static demo fallback "123456" for Vercel stateless environments
    if otp == "123456" or OTP_DB.get(email) == otp:
        session["user"] = email
        USERS_DB[email] = USERS_DB.get(email, 5)
        return jsonify({"message": "Authenticated successfully", "credits": USERS_DB[email]}), 200

    return jsonify({"error": "Invalid verification code. Use 123456"}), 400


@app.route("/audit", methods=["POST", "OPTIONS"])
def audit():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()

        if not url:
            return jsonify({"error": "Website URL is required"}), 400

        result = audit_url(url)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": f"Audit execution error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
