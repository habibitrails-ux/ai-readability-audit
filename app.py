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

    # 1. Standard JSON-LD Extraction
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

    # 2. Enhanced Open Graph & Meta Fallback (Catches all price tag variants)
    og_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'og:title'})
    og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
    og_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'og:description'})
    
    # Comprehensive check for price across multiple standards
    og_price = (
        soup.find('meta', property='product:price:amount') or
        soup.find('meta', property='og:price:amount') or
        soup.find('meta', attrs={'name': 'twitter:data1'}) or
        soup.find('meta', attrs={'itemprop': 'price'}) or
        soup.find('meta', property='schema:price')
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

    if og_data.get('name') or og_data.get('image'):
        missing = [field for field in ['name', 'image', 'description', 'price'] if field not in og_data]
        points = 50 - (len(missing) * 10)
        return {
            "score": max(10, points),
            "found": True,
            "format": "OpenGraph / Meta Tags",
            "missing_fields": missing,
            "extracted_schema": og_data
        }

    return {"score": 0, "found": False, "missing_fields": ["Product Schema & Meta Tags Missing"]}
