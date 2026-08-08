import os
import json
import re
import urllib.robotparser
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template
from concurrent.futures import ThreadPoolExecutor

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
    score = int((allowed_count / len(AI_BOTS)) * 25)
    return {"score": score, "details": status}

def check_sitemap(target_url, headers):
    parsed = urlparse(target_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    
    try:
        res = requests.get(sitemap_url, headers=headers, timeout=2)
        if res.status_code == 200 and ("xml" in res.headers.get("Content-Type", "") or "<urlset" in res.text or "<sitemapindex" in res.text):
            return {"score": 25, "found": True, "sitemap_url": sitemap_url}
    except Exception:
        pass
        
    return {"score": 0, "found": False, "sitemap_url": sitemap_url, "issue": "sitemap.xml missing or unreachable"}

def check_semantic_html(soup):
    found_tags = []
    missing_tags = []
    
    check_tags = {
        "h1": "Main Product Heading (<h1>)",
        "main": "Main Content Container (<main>)",
        "header": "Page Header (<header>)",
        "article": "Product / Article Wrapper (<article>)"
    }
    
    for tag, label in check_tags.items():
        if soup.find(tag):
            found_tags.append(tag)
        else:
            missing_tags.append(label)
            
    score = int((len(found_tags) / len(check_tags)) * 25)
    
    return {
        "score": score,
        "found_tags": found_tags,
        "missing_tags": missing_tags
    }

def extract_schema_json_ld(soup, html_content):
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

    # 1. Standard JSON-LD
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

        points = 25 - (len(missing) * 5)
        return {
            "score": max(0, points),
            "found": True,
            "format": "JSON-LD",
            "missing_fields": missing,
            "extracted_schema": product_schema
        }

    # 2. Open Graph & Meta Fallback
    og_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'og:title'})
    og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
    og_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'og:description'})
    og_price = (
        soup.find('meta', property='product:price:amount') or
        soup.find('meta', property='og:price:amount') or
        soup.find('meta', attrs={'name': 'twitter:data1'}) or
        soup.find('meta', attrs={'itemprop': 'price'})
    )

    og_data = {}
    if og_title and og_title.get('content'):
        og_data['name'] = og_title['content']
    if og_image and og_image.get('content'):
        og_data['image'] = og_image['content']
    if og_desc and og_desc.get('content'):
        og_data['description'] = og_desc['content']
    if og_price and og_price.get('content'):
        og_data['price'] = og_price['content']

    # 3. Shopify JS Regex Fallback
    if 'price' not in og_data:
        price_match = re.search(r'"price"\s*:\s*"?(\d+(?:\.\d{2})?)"?', html_content)
        if price_match:
            val = float(price_match.group(1))
            og_data['price'] = f"{val/100:.2f}" if val > 1000 else f"{val:.2f}"

    if og_data.get('name') or og_data.get('image'):
        missing = [field for field in ['name', 'image', 'description', 'price'] if field not in og_data]
        points = 25 - (len(missing) * 5)
        return {
            "score": max(5, points),
            "found": True,
            "format": "OpenGraph / Meta Tags",
            "missing_fields": missing,
            "extracted_schema": og_data
        }

    return {"score": 0, "found": False, "missing_fields": ["Product Schema & Meta Tags Missing"]}

def fetch_page_html(url, headers, scraper_key):
    try:
        res = requests.get(url, headers=headers, timeout=2.5)
        if res.status_code == 200:
            return res.text
    except Exception:
        pass

    if scraper_key:
        try:
            payload = {'api_key': scraper_key, 'url': url}
            res = requests.get('http://api.scraperapi.com', params=payload, timeout=3.5)
            if res.status_code == 200:
                return res.text
        except Exception:
            pass

    return ""

@app.route('/')
def home():
    return render_template('index.html')

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

    # Execute robots check, sitemap check, and HTML fetching concurrently
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_robots = executor.submit(check_robots_txt, url)
        future_sitemap = executor.submit(check_sitemap, url, headers)
        future_html = executor.submit(fetch_page_html, url, headers, scraper_key)

        robots_res = future_robots.result()
        sitemap_res = future_sitemap.result()
        html = future_html.result()

    if not html:
        return jsonify({
            "url": url,
            "overall_ai_score": robots_res['score'] + sitemap_res['score'],
            "summary": "Needs Optimization (Cloudflare/Bot Blocked)",
            "breakdown": {
                "bot_accessibility": robots_res,
                "sitemap_status": sitemap_res,
                "schema_json_ld": {"score": 0, "found": False, "issue": "Page content blocked by store firewall"},
                "semantic_html": {"score": 0, "found_tags": [], "missing_tags": ["Blocked by Firewall"]}
            }
        })

    soup = BeautifulSoup(html, 'html.parser')
    schema_res = extract_schema_json_ld(soup, html)
    semantic_res = check_semantic_html(soup)

    total_score = robots_res['score'] + sitemap_res['score'] + schema_res['score'] + semantic_res['score']

    return jsonify({
        "url": url,
        "overall_ai_score": total_score,
        "summary": "Ready for AI Agents" if total_score >= 80 else "Needs Optimization",
        "breakdown": {
            "bot_accessibility": robots_res,
            "sitemap_status": sitemap_res,
            "schema_json_ld": schema_res,
            "semantic_html": semantic_res
        }
    })

if __name__ == '__main__':
    app.run()
