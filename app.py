import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "super-secret-key-12345")

USERS_DB = {}

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

def audit_url(target_url):
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    try:
        parsed_url = urllib.parse.urlparse(target_url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        domain_name = parsed_url.netloc
    except Exception:
        base_domain = target_url
        domain_name = target_url

    scores = {
        "bot_accessibility": 0,
        "sitemap_status": 0,
        "schema_json_ld": 0,
        "semantic_html": 0
    }
    fixes = []

    headers = {"User-Agent": "Mozilla/5.0 (Compatible; AIReadabilityBot/1.0)"}

    # 1. Bot Accessibility
    try:
        robots_res = requests.get(f"{base_domain}/robots.txt", headers=headers, timeout=5)
        if robots_res.status_code == 200:
            if "Disallow: /" not in robots_res.text:
                scores["bot_accessibility"] = 25
            else:
                scores["bot_accessibility"] = 10
                fixes.append({
                    "title": "Fix Restrictive robots.txt Rules",
                    "issue": "Your robots.txt file contains 'Disallow: /' directive which blocks AI search crawlers.",
                    "code": "User-agent: GPTBot\nAllow: /\n\nUser-agent: Google-Extended\nAllow: /"
                })
        else:
            scores["bot_accessibility"] = 15
            fixes.append({
                "title": "Add robots.txt File",
                "issue": "No robots.txt found at domain root.",
                "code": "User-agent: *\nAllow: /\n\nSitemap: " + base_domain + "/sitemap.xml"
            })
    except Exception:
        scores["bot_accessibility"] = 10

    # 2. Sitemap Status
    try:
        sitemap_res = requests.get(f"{base_domain}/sitemap.xml", headers=headers, timeout=5)
        if sitemap_res.status_code == 200:
            scores["sitemap_status"] = 25
        else:
            scores["sitemap_status"] = 10
            fixes.append({
                "title": "Create an XML Sitemap",
                "issue": "Missing /sitemap.xml file. AI search agents need sitemaps for deep page discovery.",
                "code": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n  <url><loc>" + base_domain + "/</loc></url>\n</urlset>"
            })
    except Exception:
        scores["sitemap_status"] = 0

    # 3 & 4. Schemas and Semantic HTML
    try:
        res = requests.get(target_url, headers=headers, timeout=8)
        if res.status_code == 200 and res.text:
            soup = BeautifulSoup(res.text, "html.parser")

            # Schema JSON-LD Check
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            if json_ld_scripts:
                scores["schema_json_ld"] = 25 if len(json_ld_scripts) > 1 else 15
            else:
                scores["schema_json_ld"] = 0
                fixes.append({
                    "title": "Add Structured JSON-LD Data Schema",
                    "issue": "No JSON-LD schema found on page. Add the following schema script inside your website's <head> element:",
                    "code": f'<script type="application/ld+json">\n{{\n  "@context": "https://schema.org",\n  "@type": "WebSite",\n  "name": "{domain_name}",\n  "url": "{target_url}"\n}}\n</script>'
                })

            # Semantic HTML Check
            semantic_tags = ["header", "nav", "main", "article", "section", "footer", "aside"]
            found_tags = [tag for tag in semantic_tags if soup.find(tag)]
            if len(found_tags) >= 4:
                scores["semantic_html"] = 25
            elif len(found_tags) >= 2:
                scores["semantic_html"] = 15
            else:
                scores["semantic_html"] = 5
                fixes.append({
                    "title": "Use Semantic HTML Structural Tags",
                    "issue": "Replace generic <div> tags with semantic layout containers (<header>, <main>, <article>, <footer>) to allow LLMs to isolate main body content.",
                    "code": "<header>...</header>\n<main>\n  <article>...</article>\n</main>\n<footer>...</footer>"
                })
    except Exception:
        scores["schema_json_ld"] = 0
        scores["semantic_html"] = 0

    total_score = sum(scores.values())

    return {
        "url": target_url,
        "overall_score": total_score,
        "summary": f"Audit completed for {target_url}. Overall score is {total_score}/100.",
        "breakdown": scores,
        "fixes": fixes
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/me", methods=["GET"])
def get_current_user():
    user_email = session.get("user")
    if user_email and user_email in USERS_DB:
        return jsonify({
            "authenticated": True,
            "email": user_email,
            "credits": USERS_DB[user_email]["credits"]
        }), 200
    return jsonify({"authenticated": False}), 200


@app.route("/signup", methods=["POST", "OPTIONS"])
def signup():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    if email in USERS_DB:
        return jsonify({"error": "Account already exists."}), 400

    USERS_DB[email] = {
        "password": generate_password_hash(password),
        "credits": 5
    }
    session["user"] = email

    return jsonify({"message": "Success", "email": email, "credits": 5}), 200


@app.route("/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    user = USERS_DB.get(email)
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user"] = email
    return jsonify({"message": "Success", "email": email, "credits": user["credits"]}), 200


@app.route("/logout", methods=["POST", "OPTIONS"])
def logout():
    session.pop("user", None)
    return jsonify({"message": "Logged out"}), 200


@app.route("/audit", methods=["POST", "OPTIONS"])
def audit():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "URL required"}), 400

        result = audit_url(url)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
