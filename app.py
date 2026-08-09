import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/audit', methods=['POST'])
def audit():
    try:
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        parsed_url = urlparse(url)
        if not parsed_url.netloc:
            return jsonify({'error': 'Invalid URL provided'}), 400

        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ClarityScanAI/1.0 (AI Readability Diagnostic)'
        }

        score = 0
        checks = {
            'robots': {'status': 'Missing', 'passed': False},
            'sitemap': {'status': 'Missing', 'passed': False},
            'json_ld': {'status': 'Missing', 'passed': False},
            'semantic_html': {'status': 'Review', 'passed': False}
        }

        # 1. Check Robots.txt
        try:
            r_robots = requests.get(f"{base_url}/robots.txt", headers=headers, timeout=5)
            if r_robots.status_code == 200 and "User-agent" in r_robots.text:
                checks['robots'] = {'status': 'Found', 'passed': True}
                score += 25
        except Exception:
            pass

        # 2. Check Sitemap.xml
        try:
            r_sitemap = requests.get(f"{base_url}/sitemap.xml", headers=headers, timeout=5)
            if r_sitemap.status_code == 200 and ("xml" in r_sitemap.headers.get('Content-Type', '') or "<urlset" in r_sitemap.text or "<sitemapindex" in r_sitemap.text):
                checks['sitemap'] = {'status': 'Found', 'passed': True}
                score += 25
        except Exception:
            pass

        # 3. Check Webpage Content for JSON-LD & Semantic HTML
        try:
            response = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # JSON-LD check
                json_ld = soup.find('script', type='application/ld+json')
                if json_ld and json_ld.string and len(json_ld.string.strip()) > 0:
                    checks['json_ld'] = {'status': 'Found', 'passed': True}
                    score += 25

                # Semantic HTML check (<main>, <article>, <header>, <nav>, <section>)
                semantic_tags = soup.find_all(['main', 'article', 'header', 'nav', 'section'])
                if len(semantic_tags) >= 2:
                    checks['semantic_html'] = {'status': 'Found', 'passed': True}
                    score += 25
        except Exception:
            pass

        return jsonify({
            'url': url,
            'score': score,
            'checks': checks
        }), 200

    except Exception as e:
        return jsonify({'error': f"Audit failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
