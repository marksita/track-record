import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")
st.markdown("Discover entrepreneurs **starting or investing in companies**")

# ==================== CONFIG ====================
KNOWN_COMPANIES = {
    "tesla", "spacex", "xai", "openai",
    "anthropic", "stripe", "airbnb", "palantir"
}

RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "Crunchbase": "https://news.crunchbase.com/feed/",
}

# ==================== HELPERS ====================
def clean_title(title):
    return title.rsplit(" - ", 1)[0].strip() if " - " in title else title.strip()

def extract_company(title):
    clean = clean_title(title).lower()

    # Known companies
    for c in KNOWN_COMPANIES:
        if c in clean:
            return c.title()

    # Funding / launch patterns
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

    # Fallback: first name-like match
    fallback = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
    return fallback[0] if fallback else "Unknown"

def detect_role(text):
    text = text.lower()

    if any(k in text for k in ["founded", "launched", "started"]):
        return "Founder"
    if any(k in text for k in ["invested", "backed", "led"]):
        return "Investor"

    return "Mentioned"

def is_high_signal(text):
    keywords = ["funding", "startup", "raises", "invest", "backed", "launch"]
    return any(k in text.lower() for k in keywords)

# ==================== FETCH ====================
def fetch_google_news(query, months):
    encoded = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}+when:{months}m&hl=en-US&gl=US&ceid=US:en"
    return feedparser.parse(url).entries[:15]

# ==================== UI ====================
sources = st.sidebar.multiselect(
    "Sources",
    ["Google News", "TechCrunch", "VentureBeat", "Crunchbase"],
    default=["Google News", "TechCrunch"]
)

months = st.sidebar.slider("Lookback (months)", 1, 12, 3)

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

    for source in sources:

        if source == "Google News":
            entries = []
            for q in queries:
                entries += fetch_google_news(q, months)
        else:
            entries = feedparser.parse(RSS_FEEDS[source]).entries[:20]

        for entry in entries:

            title = entry.title or ""
            clean = clean_title(title)

            if clean in seen:
                continue
            seen.add(clean)

            # Only keep high-signal articles
            if not is_high_signal(clean):
                continue

            company = extract_company(title)
            if company is None:
                continue

            entrepreneur = extract_entrepreneur(clean)
            role = detect_role(clean)

            results.append({
                "Entrepreneur": entrepreneur,
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
