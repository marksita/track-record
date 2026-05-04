import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")

# ==================== SOURCES ====================
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "Crunchbase News": "https://news.crunchbase.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "WIRED": "https://www.wired.com/feed/rss",
    "Forbes Tech": "https://www.forbes.com/technology/feed/",
    "Business Insider": "https://www.businessinsider.com/rss",
    "Tech.eu": "https://tech.eu/feed/",
    "Startup Daily": "https://www.startupdaily.net/feed/",
    "SmartCompany": "https://www.smartcompany.com.au/feed/",
    "InnovationAus": "https://www.innovationaus.com/feed/",
    "AFR": "https://www.afr.com/rss"
}

GOOGLE_SOURCE = "Google News"
ALL_SOURCES = list(RSS_FEEDS.keys()) + [GOOGLE_SOURCE]

st.markdown(f"**Sources used:** {', '.join(ALL_SOURCES)}")

# ==================== COUNTRY ====================
COUNTRY_KEYWORDS = {
    "USA": ["us", "usa", "california", "new york"],
    "UK": ["uk", "britain", "london"],
    "Australia": ["australia", "sydney", "melbourne"],
    "India": ["india", "bangalore", "delhi"],
    "Canada": ["canada", "toronto"],
    "Europe": ["germany", "france", "spain", "eu"]
}

SOURCE_COUNTRY_MAP = {
    "Startup Daily": "Australia",
    "SmartCompany": "Australia",
    "InnovationAus": "Australia",
    "AFR": "Australia"
}

def detect_country(text, source=None):
    text_lower = text.lower()

    for country, keywords in COUNTRY_KEYWORDS.items():
        if any(k in text_lower for k in keywords):
            return country

    if source in SOURCE_COUNTRY_MAP:
        return SOURCE_COUNTRY_MAP[source]

    return "Unknown"

# ==================== SCRAPING ====================
@st.cache_data(ttl=3600)
def fetch_article_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        paragraphs = soup.find_all("p")
        return " ".join(p.get_text() for p in paragraphs)[:3000]
    except:
        return ""

# ==================== EXTRACTION ====================
def extract_entrepreneur(text):
    patterns = [
        r'([A-Z][a-z]+ [A-Z][a-z]+)[’\'s]* .*?(founded|launched|started)',
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(CEO|founder|co-founder)',
        r'([A-Z][a-z]+ [A-Z][a-z]+)[- ]backed',
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(invested|backs|led)',
        r'(?:by|from)\s+([A-Z][a-z]+ [A-Z][a-z]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    candidates = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
    blacklist = {"Google News", "Tech Crunch", "Business Insider"}

    for name in candidates:
        if name not in blacklist:
            return name

    return None

def extract_company(text):
    patterns = [
        r'([A-Z][A-Za-z0-9&\-\.\']{2,})\s+(raises|secures|launches|unveils)',
        r'(?:invests? in|backs?|acquires?|leads?)\s+([A-Z][A-Za-z0-9&\-\.\']{2,})'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            company = match.group(1)
            if company.lower() not in ["startup", "company", "firm"]:
                return company

    # fallback
    fallback = re.findall(r'([A-Z][A-Za-z0-9&\-]{3,})', text)
    return fallback[0] if fallback else None

def detect_role(text):
    text = text.lower()
    if any(k in text for k in ["founded", "launched", "started"]):
        return "Founder"
    if any(k in text for k in ["invested", "backed", "led"]):
        return "Investor"
    return "Mentioned"

# ==================== FETCH ====================
def fetch_google_news(query, months):
    encoded = urllib.parse.quote_plus(query + " Australia")
    url = f"https://news.google.com/rss/search?q={encoded}+when:{months}m&hl=en-AU&gl=AU&ceid=AU:en"
    return feedparser.parse(url).entries[:15]

# ==================== UI ====================
months = st.sidebar.slider("Lookback (months)", 1, 12, 3)

country_filter = st.sidebar.selectbox(
    "Filter by Country",
    ["All"] + list(COUNTRY_KEYWORDS.keys())
)

# ==================== MAIN ====================
if st.button("🚀 Run Discovery"):

    queries = [
        "startup raises funding Australia",
        "Australian startup raises",
        "Sydney startup funding",
        "Melbourne startup founder",
        "Australia venture capital invests",
        "Australian startup launched"
    ]

    results = []
    seen = set()

    def process(entry, source):
        title = entry.title or ""
        clean = title.split(" - ")[0].strip()

        if clean in seen:
            return
        seen.add(clean)

        article = fetch_article_text(entry.link)
        text = clean + " " + article

        entrepreneur = extract_entrepreneur(text)
        company = extract_company(text)

        # ❌ HARD FILTER UNKNOWN
        if not entrepreneur or not company:
            return

        if len(entrepreneur.split()) != 2:
            return

        role = detect_role(text)
        country = detect_country(text, source)

        if country_filter != "All" and country != country_filter:
            return

        results.append({
            "Entrepreneur": entrepreneur,
            "Role": role,
            "Company": company,
            "Title": clean,
            "Source": source,
            "Country": country,
            "Link": entry.link
        })

    # Google
    for q in queries:
        for e in fetch_google_news(q, months):
            process(e, GOOGLE_SOURCE)

    # RSS
    for source, url in RSS_FEEDS.items():
        for e in feedparser.parse(url).entries[:20]:
            process(e, source)

    # ==================== DISPLAY ====================
    if results:
        df = pd.DataFrame(results)

        counts = df["Entrepreneur"].value_counts().to_dict()
        df["Score"] = df["Entrepreneur"].map(counts)

        df = df.sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']}** — *{r['Role']}*")
            st.markdown(f"🔥 Score: {r['Score']}")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"🌍 {r['Country']} | 📡 {r['Source']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()

        st.download_button(
            "📥 Download CSV",
            df.to_csv(index=False).encode(),
            "results.csv"
        )

    else:
        st.error("No high-quality results found")
