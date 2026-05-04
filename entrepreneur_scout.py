import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
import json
from newspaper import Article

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout (AI Powered)")
st.markdown("Discover entrepreneurs **starting or investing in companies**")

# ==================== CONFIG ====================
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
MAX_AI_CALLS = 8  # prevent slowdowns

# ==================== DATA ====================
KNOWN_COMPANIES = {
    "tesla", "spacex", "xai", "openai", "anthropic",
    "stripe", "airbnb", "palantir"
}

RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "Crunchbase": "https://news.crunchbase.com/feed/",
}

# ==================== HELPERS ====================
def clean_google_title(title):
    return title.rsplit(" - ", 1)[0].strip() if " - " in title else title.strip()

def extract_company_name(title):
    clean = clean_google_title(title).lower()

    for c in KNOWN_COMPANIES:
        if c in clean:
            return c.title()

    match = re.search(r'([A-Z][A-Za-z0-9&\-\.\']{2,})\s+(raises|secures|launches)', title)
    if match:
        return match.group(1)

    return None

def extract_basic(text):
    match = re.search(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
    return match.group(1) if match else "Unknown", "Unknown"

def is_high_signal(text):
    keywords = ["funding", "startup", "raises", "invest", "backed", "launch"]
    return any(k in text.lower() for k in keywords)

# ==================== CACHED FUNCTIONS ====================
@st.cache_data(ttl=3600)
def get_article_text(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text[:3000]
    except:
        return None

@st.cache_data(ttl=3600)
def extract_with_ollama(text):
    try:
        prompt = f"""
        Extract:
        - entrepreneur
        - role (Founder or Investor)
        - company

        Return ONLY JSON:
        {{
          "entrepreneur": "",
          "role": "",
          "company": ""
        }}

        Text:
        {text}
        """

        res = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=20
        )

        output = res.json().get("response", "")
        return json.loads(output)

    except:
        return None

# ==================== FETCH ====================
def fetch_google_news(query, months):
    encoded = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}+when:{months}m&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)

    return feed.entries[:15]

# ==================== UI ====================
sources = st.sidebar.multiselect(
    "Sources",
    ["Google News", "TechCrunch", "VentureBeat", "Crunchbase"],
    default=["Google News", "TechCrunch"]
)

months = st.sidebar.slider("Lookback (months)", 1, 12, 3)

# ==================== MAIN ====================
if st.button("🚀 Run AI Discovery"):

    queries = [
        "startup raises funding",
        "founded startup",
        "invested in startup",
        "backs startup",
        "led funding round"
    ]

    results = []
    seen = set()
    ai_calls = 0

    for source in sources:

        if source == "Google News":
            entries = []
            for q in queries:
                entries += fetch_google_news(q, months)

        else:
            feed = feedparser.parse(RSS_FEEDS[source])
            entries = feed.entries[:15]

        for entry in entries:

            title = entry.title or ""
            clean = clean_google_title(title)

            if clean in seen:
                continue
            seen.add(clean)

            company = extract_company_name(title)
            name, role = extract_basic(clean)

            # 🔥 AI UPGRADE
            if (
                ai_calls < MAX_AI_CALLS
                and is_high_signal(clean)
                and (company is None or name == "Unknown")
            ):
                article = get_article_text(entry.link)

                if article:
                    ai_data = extract_with_ollama(article)

                    if ai_data:
                        name = ai_data.get("entrepreneur", name)
                        role = ai_data.get("role", role)
                        company = ai_data.get("company", company)

                        ai_calls += 1

            if company is None:
                continue

            results.append({
                "Entrepreneur": name,
                "Role": role,
                "Company": company,
                "Title": clean,
                "Link": entry.link
            })

    # ==================== DISPLAY ====================
    if results:
        df = pd.DataFrame(results)

        st.success(f"✅ Found {len(df)} results")

        for _, r in df.iterrows():
            with st.container():
                st.markdown(f"### 🏢 {r['Company']}")
                st.markdown(f"**👤 {r['Entrepreneur']}** — *{r['Role']}*")
                st.markdown(f"📰 {r['Title']}")
                st.markdown(f"[🔗 Read Article]({r['Link']})")
                st.divider()

        csv = df.to_csv(index=False).encode()
        st.download_button("📥 Download CSV", csv, "results.csv")

    else:
        st.error("No results found")
