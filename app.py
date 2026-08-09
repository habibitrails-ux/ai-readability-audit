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
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")  # Your Gmail address
app.config["MAIL_PASSWORD"] = os.environ.get(
    "MAIL_PASSWORD"
)  # 16-char Gmail App Password
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")

mail = Mail(app)

# In-memory storage for pending OTPs and verified user credits
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
            subject="Verify your email - AI Readability Audit",
            sender=("AI Readability Audit", sender_email),
            recipients=[email],
        )

        # Professional HTML Email Body
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
              background-color: #f4f6f9;
              margin: 0;
              padding: 24px;
            }}
            .container {{
              max-width: 480px;
              margin: 0 auto;
              background: #ffffff;
              border-radius: 12px;
              padding: 32px;
              border: 1px solid #e2e8f0;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            }}
            .header {{
              text-align: center;
              margin-bottom: 24px;
            }}
            .logo-text {{
              font-size: 20px;
              font-weight: 800;
              color: #0f172a;
              letter-spacing: -0.5px;
            }}
            .title {{
              font-size: 18px;
              font-weight: 600;
              color: #1e293b;
              margin-top: 16px;
              margin-bottom: 8px;
            }}
            .description {{
              font-size: 14px;
              color: #64748b;
              line-height: 1.5;
              margin-bottom: 24px;
            }}
            .code-box {{
              background-color: #f8fafc;
              border-radius: 8px;
              padding: 16px;
              text-align: center;
              margin-bottom: 24px;
              border: 1px dashed #0284c7;
            }}
            .otp-code {{
              font-size: 32px;
              font-weight: 800;
              color: #0284c7;
              letter-spacing: 6px;
              font-family: monospace;
            }}
            .footer {{
              font-size: 12px;
              color: #94a3b8;
              text-align: center;
              margin-top: 32px;
              border-top: 1px solid #f1f5f9;
              padding-top: 16px;
            }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <div class="logo-text">⚡ AI Readability Audit</div>
            </div>
            <div class="title">Verification Code</div>
            <p class="description">Please use the verification code below to sign in and access your audit credits. This code will expire in 10 minutes.</p>

            <div class="code-box">
              <div class="otp-code">{otp}</div>
            </div>

            <p class="description" style="font-size: 13px; margin-bottom: 0;">If you didn't request this code, you can safely ignore this email.</p>

            <div class="footer">
              &copy; AI Readability Diagnostic Tool. All rights reserved.
            </div>
          </div>
        </body>
        </html>
        """

        # Fallback text version for basic previewers
        msg.body = f"Your AI Readability Audit verification code is: {otp}\n\nThis code will expire in 10 minutes."

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

    # Clean up OTP after successful verification
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
