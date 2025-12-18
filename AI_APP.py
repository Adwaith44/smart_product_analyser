import os
import gradio as gr
from google import genai
from PIL import Image
import serpapi

# Setup Gemini
os.environ["GEMINI_API_KEY"] = "AIzaSyC46jY82L7Svhhlvd0D8Vf62M4NlUWufAE"
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Setup SerpAPI
SERPAPI_KEY = "4f68bf6c1878a7eadcd372bba4d824e064c413f1cadb59b6e947f9f3a0faec30"


def analyze_image(image):
    if image is None:
        return "No image provided.", gr.update(visible=False), gr.update(visible=False)

    prompt = """
    Identify this product with high precision.
    Return ONLY a raw data block with these exact keys:

    ITEM_NAME: [Brand + Model Name]
    CATEGORY: [e.g. Sneakers, Electronics, Furniture]
    CONDITION_VISUAL: [New, Used, Damaged - based on visual cues]
    COLOR: [Dominant colors]
    DISTINGUISHING_FEATURES: [Logos, scratches, unique markers]

    Do not add conversational filler. Just the data.
    """

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image]
        )
        return response.text, gr.update(visible=True), gr.update(visible=True)
    except Exception as e:
        return f"Error: {str(e)}", gr.update(visible=False), gr.update(visible=False)


def generate_sell_info(product_data):
    if not product_data or product_data.startswith("Error"):
        return "Please analyze an image first."

    prompt = f"""Based on this product data:

{product_data}

Generate a selling package with:

1. ESTIMATED PRICE: Provide a realistic market price range in GBP (£) considering condition and market demand
2. SEO-OPTIMIZED TITLE: Create a compelling, keyword-rich title (60-80 chars) for online marketplaces
3. DESCRIPTION: Write a 150-200 word SEO-optimized description that:
   - Highlights key features and condition
   - Uses relevant keywords naturally
   - Creates urgency and appeal
   - Mentions compatible uses or target audience
   - Includes condition details

Format the response clearly with headers for each section."""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Error generating sell info: {str(e)}"


def search_products_serpapi(search_query):
    try:
        client = serpapi.Client(api_key=SERPAPI_KEY)
        params = {
            "engine": "google_shopping",
            "q": search_query,
            "location": "United Kingdom",
            "hl": "en",
            "gl": "uk"
        }

        results = client.search(params).as_dict()
        products = []

        for item in results.get("shopping_results", [])[:25]:
            price = item.get("extracted_price", 0)
            if not price and item.get("price"):
                import re
                price_match = re.search(r'[\d,]+\.?\d*', item.get("price", ""))
                if price_match:
                    price = float(price_match.group().replace(',', ''))

            rating = item.get("rating")
            if not rating or rating == "N/A":
                continue

            reviews = item.get("reviews", 0)
            if not reviews or reviews == 0:
                continue

            title = item.get("title", "Unknown Product").lower()

            exclude_keywords = [
                'sample', 'tester', 'miniature', 'mini', 'trial size',
                'vial', 'demo', 'display model', 'floor model',
                'used', 'refurbished', 'parts only', 'for parts',
                'damaged', 'faulty', 'broken', 'empty'
            ]

            if any(keyword in title for keyword in exclude_keywords):
                continue

            bundle_keywords = [
                'bundle', 'gift set', 'gift box', 'combo', 'pack of',
                'coffret', 'set of', 'kit', 'collection'
            ]

            is_bundle = False
            for keyword in bundle_keywords:
                if keyword in title:
                    if keyword == 'set of' or 'gift' in title or 'bundle' in title or 'combo' in title:
                        is_bundle = True
                        break

            if is_bundle:
                continue

            products.append({
                "title": item.get("title", "Unknown Product"),
                "price": price,
                "link": item.get("link", "#"),
                "source": item.get("source", "Unknown Retailer"),
                "thumbnail": item.get("thumbnail", ""),
                "rating": rating,
                "reviews": reviews
            })

        if not products:
            return None, "No products with ratings and reviews found"

        products.sort(key=lambda x: x['price'] if x['price'] else float('inf'))

        valid_prices = [p['price'] for p in products if p['price'] > 0]
        if len(valid_prices) >= 3:
            valid_prices_sorted = sorted(valid_prices)
            median_price = valid_prices_sorted[len(valid_prices_sorted) // 2]
            min_acceptable = median_price * 0.4
            max_acceptable = median_price * 2.5

            filtered_products = [
                p for p in products
                if min_acceptable <= p['price'] <= max_acceptable
            ]

            if len(filtered_products) >= 3:
                products = filtered_products

        return products[:5], None

    except Exception as e:
        return None, f"SerpAPI Error: {str(e)}"


def generate_buy_links(product_data):
    if not product_data or product_data.startswith("Error"):
        return "Please analyze an image first."

    search_prompt = f"""Based on this product data:

{product_data}

Extract the most specific search terms to find this exact product online.
Return ONLY the product name with brand and model (no extra text), for example:
- "Nike Air Max 90 White"
- "Apple MacBook Pro M2 14-inch"
- "Ray-Ban Wayfarer Sunglasses"

Be specific with brand and model."""

    try:
        search_response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=search_prompt
        )

        search_query = search_response.text.strip().replace('\n', ' ')
        products, error = search_products_serpapi(search_query)

        if error:
            return f"""## ⚠️ {error}

**Searched for:** {search_query}

**Manual search links:**
- [Amazon UK](https://www.amazon.co.uk/s?k={search_query.replace(' ', '+')})
- [eBay UK](https://www.ebay.co.uk/sch/i.html?_nkw={search_query.replace(' ', '+')}&_sop=15)
- [Google Shopping](https://www.google.com/search?tbm=shop&q={search_query.replace(' ', '+')})
"""

        if not products:
            return f"""## 🔍 No products found for: **{search_query}**

Try these manual searches:
- [Amazon UK](https://www.amazon.co.uk/s?k={search_query.replace(' ', '+')})
- [eBay UK](https://www.ebay.co.uk/sch/i.html?_nkw={search_query.replace(' ', '+')}&_sop=15)
- [Google Shopping](https://www.google.com/search?tbm=shop&q={search_query.replace(' ', '+')})
"""

        output = f"""## 🔍 Search Query: **{search_query}**

## 💰 Found {len(products)} Products (Sorted by Price - Cheapest First)

"""

        for i, product in enumerate(products, 1):
            price_display = f"£{product['price']:.2f}" if product['price'] else "Price not available"
            rating_display = f"⭐ {product['rating']}" if product['rating'] != "N/A" else ""
            reviews_display = f"({product['reviews']} reviews)" if product['reviews'] else ""

            output += f"""### {i}. [{product['title'][:70]}...]({product['link']})

**💷 Price:** {price_display} | **🏪 Retailer:** {product['source']} {rating_display} {reviews_display}

---

"""

        return output

    except Exception as e:
        return f"""## ⚠️ Error searching for products

**Error details:** {str(e)}

Try searching manually:
- [Amazon UK](https://www.amazon.co.uk/)
- [eBay UK](https://www.ebay.co.uk/)
- [Google Shopping](https://www.google.com/search?tbm=shop)
"""


# Simple, clean CSS
css = """
.gradio-container {
    max-width: 100% !important;
    padding: 40px !important;
}

.gr-button-primary {
    background: #1a73e8 !important;
    border: none !important;
}

.gr-button-secondary {
    background: #34a853 !important;
    border: none !important;
    color: white !important;
}
"""

# Build Interface
with gr.Blocks(css=css) as demo:
    gr.Markdown("# 🛍️ Smart Scan")
    gr.Markdown("## 📸 Step 1: Scan Your Product")

    with gr.Row():
        with gr.Column():
            img_input = gr.Image(type="pil", label="Upload or Capture Product Photo", sources=["upload", "webcam"])
            scan_btn = gr.Button("🔍 Analyze Image", variant="primary", size="lg")
        with gr.Column():
            raw_data_output = gr.Textbox(label="Product Data", lines=10, placeholder="Product details will appear here...")

    gr.Markdown("## 💡 Step 2: Choose Your Action")

    with gr.Row():
        sell_btn = gr.Button("💰 I Want to SELL This", variant="secondary", size="lg", visible=False)
        buy_btn = gr.Button("🛒 I Want to BUY This", variant="secondary", size="lg", visible=False)

    sell_output = gr.Textbox(label="Selling Information", lines=12, visible=False)
    buy_output = gr.Markdown(label="Buying Guide", visible=False)

    scan_btn.click(fn=analyze_image, inputs=img_input, outputs=[raw_data_output, sell_btn, buy_btn])
    sell_btn.click(fn=generate_sell_info, inputs=raw_data_output, outputs=sell_output).then(lambda: gr.update(visible=True), outputs=sell_output)
    buy_btn.click(fn=generate_buy_links, inputs=raw_data_output, outputs=buy_output).then(lambda: gr.update(visible=True), outputs=buy_output)

demo.launch()