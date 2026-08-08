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
    # 1. Direct fetch (fastest)
    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code == 200:
            html = response.text
    except Exception:
        pass

    # 2. ScraperAPI Proxy Fallback if direct fetch blocked or failed
    if not html and scraper_key:
        try:
            # Using fast standard proxy without JS rendering overhead
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
