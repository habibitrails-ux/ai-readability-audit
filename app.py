import os
import random
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, session
from flask_mail import Mail, Message
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key-change-me")

# SMTP Mail Setup (Configured via Vercel Environment Variables)
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")  # Your email address
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")  # 16-char App Password
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")

mail = Mail(app)

# Storage for pending OTPs and verified user credits
PENDING_OTPS = {}
USERS_DB = {}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Valid email address is required"}), 400

    otp = str(random.randint(100000, 999999))
    PENDING_OTPS[email] = otp

    if not app.config["MAIL_USERNAME"]:
        print(f"[DEVELOPMENT MODE] OTP for {email}: {otp}")
        return jsonify(
            {
                "success": True,
                "message": "OTP generated (Check server logs in dev mode)",
            }
        )

    try:
        sender_email = app.config["MAIL_USERNAME"]
        msg = Message(
            subject="Your Verification Code",
            sender=("AI Readability Audit", sender_email),
            recipients=[email],
            body=(
                f"Your 6-digit verification code is: {otp}\n\n"
                "This code will expire in 10 minutes. If you did not request this code, please ignore this email."
            ),
        )
        mail.send(msg)
        return jsonify({"success": True, "message": "OTP sent to your email!"})
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {str(e)}"}), 500


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    user_otp = data.get("otp", "").strip()

    if PENDING_OTPS.get(email) != user_otp:
        return jsonify({"error": "Invalid or expired verification code"}), 400

    # Remove code after verification
    del PENDING_OTPS[email]

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

        bot_score = 25
        try:
            robots_res = requests.get(f"{base_url}/robots.txt", timeout=5)
            if robots_res.status_code == 200 and "Disallow: /" in robots_res.text:
                bot_score = 10
        except Exception:
            bot_score = 15

        sitemap_score = 0
        try:
            sitemap_res = requests.get(f"{base_url}/sitemap.xml", timeout=5)
            if sitemap_res.status_code == 200:
                sitemap_score = 25
        except Exception:
            sitemap_score = 0

        schema_scripts = soup.find_all("script", type="application/ld+json")
        json_ld_score = 25 if len(schema_scripts) > 0 else 0

        semantic_tags = soup.find_all(
            ["header", "main", "footer", "article", "section", "nav"]
        )
        semantic_score = 25 if len(semantic_tags) >= 3 else 10

        overall_score = bot_score + sitemap_score + json_ld_score + semantic_score

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
