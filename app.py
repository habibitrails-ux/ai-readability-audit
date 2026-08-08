import json
import urllib.robotparser
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify

app = Flask(__name__)

AI_BOTS = ["GPTBot", "PerplexityBot", "ClaudeBot", "Google-Extended", "ChatGPT-User"]

def check_robots_txt(target_url):
    parsed = urlparse(target_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    
    status = {}
    try:
        rp.read()
        for bot in AI_BOTS:
            status[bot] = rp.can_fetch(bot, target_url)
    except Exception:
        status = {bot: True for bot in AI_BOTS}
        
    allowed_count = sum(1 for allowed in status.values() if allowed)
    score = int((allowed_count / len(AI_BOTS)) * 50)
    return {"score": score, "details": status}

def extract_schema_json_ld(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    scripts = soup.find_all('script', type='application/ld+json')
    
    product_schema = None

    def search_for_product(data):
        if isinstance(data, dict):
            schema_type = data.get('@type')
            if schema_type == 'Product' or (isinstance(schema_type, list) and 'Product' in schema_type):
                return data
            for value in data.values():
                res = search_for_product(value)
                if res:
                    return res
        elif isinstance(data, list):
            for item in data:
                res = search_for_product(item)
                if res:
                    return res
        return None

    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            found = search_for_product(data)
            if found:
                product_schema = found
                break
        except (json.JSONDecodeError, TypeError):
            continue

    if not product_schema:
        return {"score": 0, "found": False, "missing_fields": ["Product Schema Missing or Client-Rendered"]}

    required_fields = ['name', 'image', 'description', 'offers']
    missing = [field for field in required_fields if field not in product_schema]
    
    offers = product_schema.get('offers', {})
    if isinstance(offers, list) and len(offers) > 0:
        offers = offers[0]
    
    if isinstance(offers, dict):
        if 'price' not in offers and 'lowPrice' not in offers:
            missing.append('offers.price')
        if 'availability' not in offers:
            missing.append('offers.availability')

    points = 50 - (len(missing) * 10)
    return {
        "score": max(0, points),
        "found": True,
        "missing_fields": missing,
        "extracted_schema": product_schema
    }

@app.route('/audit', methods=['GET', 'POST'])
def run_audit():
    if request.method == 'GET':
        url = request.args.get('url')
    else:
        data = request.get_json(silent=True) or {}
        url = data.get('url')

    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text
    except Exception as e:
        return jsonify({"error": f"Failed to fetch website: {str(e)}"}), 500

    robots_res = check_robots_txt(url)
    schema_res = extract_schema_json_ld(html)
    total_score = robots_res['score'] + schema_res['score']

    return jsonify({
        "url": url,
        "overall_ai_score": total_score,
        "summary": "Ready for AI Agents" if total_score >= 80 else "Needs Optimization",
        "breakdown": {
            "bot_accessibility": robots_res,
            "schema_json_ld": schema_res
        }
    })

if __name__ == '__main__':
    app.run()
