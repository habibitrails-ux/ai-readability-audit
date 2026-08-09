import os
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__, template_folder='templates')

# Flask secret key required for secure session signing across Vercel serverless requests
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key-ai-readability")

# In-memory user database
USERS_DB = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/me', methods=['GET'])
def get_current_user():
    user_email = session.get('user')
    if user_email and user_email in USERS_DB:
        return jsonify({
            "authenticated": True,
            "email": user_email,
            "credits": USERS_DB[user_email]["credits"]
        }), 200
    return jsonify({"authenticated": False}), 200

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    if email in USERS_DB:
        return jsonify({"error": "Account already exists with this email."}), 400

    USERS_DB[email] = {
        "password": password,
        "credits": 5
    }
    session['user'] = email
    return jsonify({"message": "Signup successful", "email": email, "credits": 5}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    user = USERS_DB.get(email)
    if not user or user['password'] != password:
        return jsonify({"error": "Invalid email or password."}), 401

    session['user'] = email
    return jsonify({"message": "Login successful", "email": email, "credits": user['credits']}), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "Logged out"}), 200

@app.route('/audit', methods=['POST'])
def run_audit():
    user_email = session.get('user')
    if not user_email or user_email not in USERS_DB:
        return jsonify({"error": "Authentication required. Please sign in."}), 401

    if USERS_DB[user_email]["credits"] <= 0:
        return jsonify({"error": "Insufficient credits. Please upgrade your account."}), 403

    data = request.get_json() or {}
    target_url = data.get('url', '').strip()

    if not target_url:
        return jsonify({"error": "Please enter a target URL."}), 400

    # Deduct credit
    USERS_DB[user_email]["credits"] -= 1

    # Mock Diagnostic Analysis
    result = {
        "overall_score": 85,
        "summary": "Your domain is well-indexed by AI search engines, but missing essential JSON-LD organization schema.",
        "breakdown": {
            "bot_accessibility": 25,
            "sitemap_status": 25,
            "schema_json_ld": 15,
            "semantic_html": 20
        },
        "fixes": [
            {
                "title": "Add Missing JSON-LD WebSite Schema",
                "issue": "AI search engines require JSON-LD schema to accurately index organization details.",
                "code": '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "WebSite",\n  "name": "My Business",\n  "url": "' + target_url + '"\n}\n</script>'
            }
        ]
    }

    return jsonify(result), 200

if __name__ == '__main__':
    app.run(debug=True)
