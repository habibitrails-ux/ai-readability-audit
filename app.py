import re
import json
import urllib.robotparser
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
import openai

app = Flask(__name__)

# List of major AI Shopping & Answer Engine Bots
AI_BOTS = ["GPTBot", "PerplexityBot", "ClaudeBot", "Google-Extended", "ChatGPT-User"]

def check_robots_txt(target_url):
    """Check if major AI bots are blocked in robots.txt."""
    parsed = urlparse(target_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    
    status = {}
    try:
        rp.read()
        for bot in AI_BOTS:
            # Check access to the specific product path or root
            status[bot] = rp.can_fetch(bot, target_url)
    except Exception:
        # If robots.txt fails to load or doesn't exist, assume allowed
        status = {bot: True for bot in AI_BOTS}
        
    allowed_count = sum(1 for allowed in status.values() if allowed)
    score = int((allowed_count / len(AI_BOTS)) * 25)
    return {"score": score, "details": status}

def extract_schema_json_ld(html_content):
    """Extract and validate schema.org Product JSON-LD."""
    soup = BeautifulSoup(html_content, 'html.parser')
    scripts = soup.find_all('script', type='application/ld+json')
    
    product_schema = None
    for script in scripts:
        try:
            data = json.loads(script.string)
            # Handle both single objects and @graph arrays
            items = data.get('@graph', [data]) if isinstance(data, dict) else data
            if isinstance(items, list):
                for item in items:
                    if item.get('@type') == 'Product':
                        product_schema = item
                        break
            elif isinstance(items, dict) and items.get('@type') == 'Product':
                product_schema = items
                break
        except (json.JSONDecodeError, TypeError):
            continue

    if not product_schema:
        return {"score": 0, "found": False, "missing_fields": ["Product Schema Missing Entirely"]}

    # Core fields required for AI Shopping agents
    required_fields = ['name', 'image', 'description', 'offers']
    missing = [field for field in required_fields if field not in product_schema]
    
    # Check inner offer fields (price, availability)
    offers = product_schema.get('offers', {})
    if isinstance(offers, list) and len(offers) > 0:
        offers = offers[0]
    
    if isinstance(offers, dict):
        if 'price' not in offers and 'lowPrice' not in offers:
            missing.append('offers.price')
        if 'availability' not in offers:
            missing.append('offers.availability')

    points = 40 - (len(missing) * 8)
    return {
        "score": max(0, points),
        "found": True,
        "missing_fields": missing,
        "extracted_schema": product_schema
    }

def test_llm_parsing(text_content):
    """Simulate an LLM attempting to extract product details from raw text."""
    # Truncate text to avoid excessive token use
    sample_text = text_content[:3000]
    
    prompt = f"""
    Extract product details from this e-commerce text into a simple JSON format with keys:
    'title', 'price', 'in_stock' (boolean). If a value is not found, set it to null.
    
    Text:
    {sample_text}
    """
    
    try:
        # Calls OpenAI API to simulate real-world AI Agent parsing
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )
        extracted = json.loads(response.choices[0].message.content)
        
        # Deduct points if LLM fails to detect basic info due to bad DOM layout
        null_count = sum(1 for v in extracted.values() if v is None)
        score = 35 - (null_count * 10)
        return {"score": max(0, score), "extracted_data": extracted}
    except Exception as e:
        return {"score": 0, "error": "LLM Parsing Failed"}

@app.route('/audit', methods=['GET', 'POST'])
def run_audit():
    if request.method == 'GET':
        url = request.args.get('url')
    else:
        data = request.get_json(silent=True) or {}
        url = data.get('url')

    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    headers = {'User-Agent': 'AIAgentReadabilityBot/1.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text
    except Exception as e:
        return jsonify({"error": f"Failed to fetch website: {str(e)}"}), 500

    # Clean HTML text for LLM test
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style"]):
        script.extract()
    clean_text = soup.get_text(separator=' ', strip=True)

    # Run Diagnostic Modules
    robots_res = check_robots_txt(url)
    schema_res = extract_schema_json_ld(html)
    llm_res = test_llm_parsing(clean_text)

    total_score = robots_res['score'] + schema_res['score'] + llm_res['score']

    return jsonify({
        "url": url,
        "overall_ai_score": total_score,
        "summary": "Ready for AI Agents" if total_score >= 80 else "Needs Optimization",
        "breakdown": {
            "bot_accessibility": robots_res,
            "schema_json_ld": schema_res,
            "llm_parseability": llm_res
        }
    })

if __name__ == '__main__':
    app.run(port=5000)
