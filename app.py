import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "super-secret-key-12345")

# Mock User Store for OTP/Credits (In-Memory for demonstration)
USERS_DB = {}
OTP_DB = {}

def audit_url(target_url):
    """
    Audits a given URL for AI Readability based on 4 pillars:
    1. Bot Accessibility (robots.txt permissions)
    2. Sitemap Status (sitemap.xml check)
    3. Schema JSON-LD (structured data presence)
    4. Semantic HTML (HTML tags usage)
    """
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    parsed_url = urllib.parse.urlparse(target_url)
    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

    scores = {
        "bot_accessibility": 0,
        "sitemap_status": 0,
        "schema_json_ld": 0,
        "semantic_html": 0
    }

    # 1. Check Bot Accessibility via robots.txt
    try:
        robots_res = requests.get(f"{base_domain}/robots.txt", timeout=5)
        if robots_res.status_code == 200:
            if "Disallow: /" not in robots_res.text:
                scores["bot_accessibility"] = 25
            else:
                scores["bot_accessibility"] = 10
        else:
            scores["bot_accessibility"] = 15
    except Exception:
        scores["bot_accessibility"] = 10

    # 2. Check Sitemap Status
    try:
        sitemap_res = requests.get(f"{base_domain}/sitemap.xml", timeout=5)
        if sitemap_res.status_code == 200:
            scores["sitemap_status"] = 25
        else:
            scores["sitemap_status"] = 10
    except Exception:
        scores["sitemap_status"] = 0

    # Fetch main HTML target page for DOM parsing
    html_content = ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Compatible; AIReadabilityBot/1.0)"}
        res = requests.get(target_url, headers=headers, timeout=8)
        if res.status_code == 200:
            html_content = res.text
    except Exception:
        pass

    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")

        # 3. Check JSON-LD Schemas
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        if json_ld_scripts:
            scores["schema_json_ld"] = 25 if len(json_ld_scripts) > 1 else 15
        else:
            scores["schema_json_ld"] = 0

        # 4. Check Semantic HTML Tags
        semantic_tags = ["header", "nav", "main", "article", "section", "footer", "aside"]
        found_tags = [tag for tag in semantic_tags if soup.find(tag)]
        if len(found_tags) >= 4:
            scores["semantic_html"] = 25
        elif len(found_tags) >= 2:
            scores["semantic_html"] = 15
        else:
            scores["semantic_html"] = 5
    else:
        scores["schema_json_ld"] = 0
        scores["semantic_html"] = 0

    total_score = sum(scores.values())

    summary = (
        f"Audit completed for {target_url}. Found {scores['schema_json_ld']} pts in JSON-LD schemas "
        f"and {scores['semantic_html']} pts in semantic HTML structures."
    )

    return {
        "url": target_url,
        "overall_score": total_score,
        "summary": summary,
        "breakdown": scores
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Dummy OTP generation for demonstration
    OTP_DB[email] = "123456"
    return jsonify({"message": "OTP sent successfully (Use 123456)"}), 200


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    otp = data.get("otp", "").strip()

    if OTP_DB.get(email) == otp:
        session["user"] = email
        USERS_DB[email] = USERS_DB.get(email, 5)  # Give 5 initial credits
        return jsonify({"message": "Authenticated", "credits": USERS_DB[email]}), 200

    return jsonify({"error": "Invalid verification code"}), 400


@app.route("/audit", methods=["POST"])
def audit():
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "Website URL is required"}), 400

    result = audit_url(url)
    return jsonify(result), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
