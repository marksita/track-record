import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse

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
    "Business Insider Tech": "https://www.businessinsider.com/rss",
    "Tech.eu": "https://tech.eu/feed/",
}

GOOGLE_SOURCE = "Google News"
ALL_SOURCES = list(RSS_FEEDS.keys()) + [GOOGLE_SOURCE]

st.markdown(f"**Sources used:** {', '.join(ALL_SOURCES)}")

# ==================== COUNTRY DETECTION ====================
COUNTRY_KEYWORDS = {
    "USA": ["us", "usa", "california", "new york", "silicon valley"],
    "UK": ["uk", "britain", "london"],
    "Australia": ["australia", "sydney", "melbourne"],
    "India": ["india", "bangalore", "delhi"],
    "Canada": ["canada", "toronto", "vancouver"],
    "Europe": ["germany", "france", "spain", "eu", "europe"]
}

def detect_country(text):
    text_lower = text.lower()
    for country, keywords in COUNTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return country
    return "Unknown"

# ==================== CONFIG ====================
KNOWN_COMPANIES = {
    "tesla", "spacex", "xai", "openai",
    "anthropic", "stripe", "airbnb", "palantir"
}

# ==================== HELPERS ====================
def clean_title(title):
    return title.rsplit(" - ", 1)[0].strip() if " - " in title else title.strip()

def extract_company(title):
    clean = clean_title(title).lower()

    for c in KNOWN_COMPANIES:
        if c in clean:
            return c.title()

    patterns = [
        r'([A-Z][A-Za-z0-9&\-\.\']{2,})\s+(raises|secures|launches|unveils)',
        r'(?:invests? in|backs?|acquires?|leads?)\s+([A-Z][A-Za-z0-9&\-\.\']{2,})'
    ]

    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            company = match.group(1)
            if company.lower() in ["startup", "company", "firm", "round", "funding"]:
                continue
            return company

    return None

def extract_entrepreneur(text):
    patterns = [
        r'([A-Z][a-z]+ [A-Z][a-z]+)[’\'s]* .*?(launches|founds|starts)',
        r'([A-Z][a-z]+ [A-Z][a-z]+)[- ]backed',
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(invests|backs|led)',
        r'(?:by|from)\s+([A-Z][a-z]+ [A-Z][a-z]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    fallback = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
    return fallback[0] if fallback else "Unknown"

def detect_role(text):
    text = text.lower()

    if any(k in text for k in ["founded", "launched", "started"]):
        return "Founder"
    if any(k in text for k in ["invested", "backed", "led"]):
        return "Investor"

    return "Mentioned"

# ==================== FETCH ====================
def fetch_google_news(query, months):
    encoded = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}+when:{months}m&hl=en-US&gl=US&ceid=US:en"
    return feedparser.parse(url).entries[:15]

# ==================== UI ====================
months = st.sidebar.slider("Lookback (months)", 1, 12, 3)

country_filter = st.sidebar.selectbox(
    "Filter by Country",
    ["All"] + list(COUNTRY_KEYWORDS.keys()) + ["Unknown"]
)

# ==================== MAIN ====================
if st.button("🚀 Run Discovery"):

    queries = [
        "startup raises funding",
        "founded startup",
        "launched startup",
        "invested in startup",
        "backs startup",
        "led funding round"
    ]

    results = []
    seen = set()

    # ===== GOOGLE NEWS =====
    for q in queries:
        entries = fetch_google_news(q, months)

        for entry in entries:
            title = entry.title or ""
            clean = clean_title(title)

            if clean in seen:
                continue
            seen.add(clean)

            company = extract_company(title)
            if company is None:
                continue

            entrepreneur = extract_entrepreneur(clean)
            role = detect_role(clean)
            country = detect_country(clean)

            if country_filter != "All" and country != country_filter:
                continue

            results.append({
                "Entrepreneur": entrepreneur,
                "Role": role,
                "Company": company,
                "Title": clean,
                "Source": GOOGLE_SOURCE,
                "Country": country,
                "Link": entry.link
            })

    # ===== RSS FEEDS =====
    for source_name, url in RSS_FEEDS.items():
        entries = feedparser.parse(url).entries[:20]

        for entry in entries:
            title = entry.title or ""
            clean = clean_title(title)

            if clean in seen:
                continue
            seen.add(clean)

            company = extract_company(title)
            if company is None:
                continue

            entrepreneur = extract_entrepreneur(clean)
            role = detect_role(clean)
            country = detect_country(clean)

            if country_filter != "All" and country != country_filter:
                continue

            results.append({
                "Entrepreneur": entrepreneur,
                "Role": role,
                "Company": company,
                "Title": clean,
                "Source": source_name,
                "Country": country,
                "Link": entry.link
            })

    # ==================== DISPLAY ====================
    if results:
        df = pd.DataFrame(results)

        df = df[df["Entrepreneur"] != "Unknown"]

        counts = df["Entrepreneur"].value_counts().to_dict()
        df["Score"] = df["Entrepreneur"].map(counts)

        df = df.sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} results")

        for _, r in df.iterrows():
            with st.container():
                st.markdown(f"### 🏢 {r['Company']}")
                st.markdown(f"**👤 {r['Entrepreneur']}** — *{r['Role']}*")
                st.markdown(f"🔥 Score: {r['Score']}")
                st.markdown(f"📰 {r['Title']}")
                st.markdown(f"🌍 {r['Country']} | 📡 {r['Source']}")
                st.markdown(f"[🔗 Read Article]({r['Link']})")
                st.divider()

        csv = df.to_csv(index=False).encode()
        st.download_button("📥 Download CSV", csv, "results.csv")

    else:
        st.error("No results found")
