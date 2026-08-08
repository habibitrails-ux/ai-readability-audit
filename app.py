import os
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

    # 1. Try extracting standard JSON-LD
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

    if product_schema:
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
            "format": "JSON-LD",
            "missing_fields": missing,
            "extracted_schema": product_schema
        }

    # 2. Fallback: Check Open Graph Meta Tags
    og_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'og:title'})
    og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
    og_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'og:description'})
    og_price = soup.find('meta', property='product:price:amount') or soup.find('meta', attrs={'name': 'twitter:label1'})

    og_data = {}
    if og_title and og_title.get('content'):
        og_data['name'] = og_title['content']
    if og_image and og_image.get('content'):
        og_data['image'] = og_image['content']
    if og_desc and og_desc.get('content'):
        og_data['description'] = og_desc['content']
    if og_price and og_price.get('content'):
        og_data['price'] = og_price['content']

    if og_data.get('name') or og_data.get('image'):
        missing = [field for field in ['name', 'image', 'description', 'price'] if field not in og_data]
        points = 35 - (len(missing) * 10)
        return {
            "score": max(10, points),
            "found": True,
            "format": "OpenGraph Meta Tags",
            "missing_fields": missing,
            "extracted_schema": og_data
        }

    return {"score": 0, "found": False, "missing_fields": ["Product Schema & Meta Tags Missing"]}

@app.route('/audit', methods=['GET', 'POST'])
def run_audit():
    if request.method == 'GET':
        url = request.args.get('url')
    else:
        data = request.get_json(silent=True) or {}
        url = data.get('url')

    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    scraper_key = os.environ.get('SCRAPER_API_KEY')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    html = ""
    # Direct fetch first
    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code == 200:
            html = response.text
    except Exception:
        pass

    # ScraperAPI Proxy Fallback if direct fetch blocked or failed
    if not html and scraper_key:
        try:
            payload = {'api_key': scraper_key, 'url': url}
            response = requests.get('http://api.scraperapi.com', params=payload, timeout=12)
            html = response.text
        except Exception as e:
            return jsonify({"error": f"Failed to fetch website: {str(e)}"}), 500

    if not html:
        return jsonify({"error": "Failed to retrieve page content within timeout limit."}), 500

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
