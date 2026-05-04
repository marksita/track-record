import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re
import urllib.parse

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")
st.markdown("Discover entrepreneurs **starting or investing in companies**")

# ==================== Known Entrepreneurs ====================
ALL_ENTREPRENEURS = {
    "Elon Musk", "Sam Altman", "Marc Andreessen", "Peter Thiel", "Garry Tan",
    "Mark Cuban", "David Sacks", "Chamath Palihapitiya", "Alex Karp",
    "Patrick Collison", "Vinod Khosla", "Dario Amodei", "Jason Calacanis",
    "Keith Rabois", "Reid Hoffman"
}

KNOWN_COMPANIES = {
    "tesla", "spacex", "xai", "neuralink", "openai",
    "anthropic", "stripe", "airbnb", "palantir"
}

# ==================== RSS SOURCES ====================
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "SiliconANGLE": "https://siliconangle.com/feed/",
    "Crunchbase": "https://news.crunchbase.com/feed/",
}

# ==================== Helpers ====================
def clean_google_title(title):
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title.strip()

def extract_company_name(title):
    if not title:
        return None

    clean_title = clean_google_title(title).lower()

    for company in KNOWN_COMPANIES:
        if company in clean_title:
            return company.title()

    patterns = [
        r'([A-Z][A-Za-z0-9&\-\.\']{2,})\s+(?:raises|secures|announces|launches|unveils)',
        r'(?:invests? in|backs?|acquires?|leads?)\s+([A-Z][A-Za-z0-9&\-\.\']{2,})',
    ]

    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            company = match.group(1).strip()

            if company.lower() in ["startup", "company", "firm", "round", "funding"]:
                continue

            if len(company) < 3:
                continue

            return company

    return None

def extract_entrepreneur_and_action(text):
    patterns = [
        (r'([A-Z][a-z]+ [A-Z][a-z]+)[’\'s]* .*?(launches|founds|starts)', "Founder"),
        (r'([A-Z][a-z]+ [A-Z][a-z]+)[- ]backed', "Investor"),
        (r'([A-Z][a-z]+ [A-Z][a-z]+).*?(invests|backs|led)', "Investor"),
        (r'(invested|backed|led).*?by ([A-Z][a-z]+ [A-Z][a-z]+)', "Investor"),
    ]

    for pattern, role in patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) >= 2 and role == "Investor":
                name = match.group(2)
            else:
                name = match.group(1)
            return name.strip(), role

    return "Unknown", "Unknown"

def is_high_signal(name):
    return name in ALL_ENTREPRENEURS

# ==================== Fetch RSS ====================
def fetch_rss_feed(feed_url):
    try:
        feed = feedparser.parse(feed_url)
        results = []

        for entry in feed.entries[:20]:
            title = entry.title or ""
            clean_title = clean_google_title(title)

            company = extract_company_name(title)
            if company is None:
                continue

            entrepreneur, role = extract_entrepreneur_and_action(clean_title)

            results.append({
                "Entrepreneur": entrepreneur,
                "Role": role,
                "Company": company,
                "Description": clean_title,
                "Published": entry.published if hasattr(entry, 'published') else "Recent",
                "Source": feed.feed.title if hasattr(feed.feed, 'title') else "RSS",
                "Link": entry.link
            })

        return results

    except:
        return []

# ==================== Fetch Google ====================
def fetch_google_news(query, days=30):
    try:
        # Convert days → months (Google prefers this)
        months = max(1, int(days / 30))

        encoded_query = urllib.parse.quote_plus(query)

        rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:{months}m&hl=en-US&gl=US&ceid=US:en"

        feed = feedparser.parse(rss_url)
        results = []

        for entry in feed.entries[:15]:
            title = entry.title or ""
            clean_title = clean_google_title(title)

            company = extract_company_name(title)
            if company is None:
                continue

            entrepreneur, role = extract_entrepreneur_and_action(clean_title)

            results.append({
                "Entrepreneur": entrepreneur,
                "Role": role,
                "Company": company,
                "Description": clean_title,
                "Published": entry.published if hasattr(entry, 'published') else "Recent",
                "Source": "Google News",
                "Link": entry.link
            })

        return results

    except:
        return []

# ==================== UI ====================
st.sidebar.header("Sources")

selected_sources = st.sidebar.multiselect(
    "Select Sources",
    ["RSS: TechCrunch", "RSS: VentureBeat", "RSS: SiliconANGLE", "RSS: Crunchbase", "Google News"],
    default=["RSS: TechCrunch", "Google News"]
)

lookback = st.sidebar.slider("Lookback (days)", 7, 365, 30)
st.sidebar.caption("Tip: Larger lookback = more results but slightly noisier")

# ==================== SEARCH ====================
if st.button("🚀 Find Entrepreneurs", type="primary"):

    queries = [
        "startup raises funding",
        "founded startup",
        "launched startup",
        "started company",
        "invested in startup",
        "backs startup",
        "led funding round"
    ]

    all_results = []
    seen = set()
    progress_bar = st.progress(0)

    for idx, source in enumerate(selected_sources):
        with st.spinner(f"Fetching from {source}..."):

            if "RSS" in source:
                feed_name = source.replace("RSS: ", "")
                feed_url = RSS_FEEDS.get(feed_name)

                results = fetch_rss_feed(feed_url) if feed_url else []

            elif source == "Google News":
                results = []
                for q in queries:
                    results.extend(fetch_google_news(q, lookback))

            else:
                results = []

            for item in results:
                key = item["Description"]

                if key not in seen:
                    seen.add(key)
                    all_results.append(item)

        progress_bar.progress((idx + 1) / len(selected_sources))

    if all_results:
        df = pd.DataFrame(all_results)

        df["Priority"] = df["Entrepreneur"].apply(lambda x: 1 if is_high_signal(x) else 0)
        df = df.sort_values(by="Priority", ascending=False)

        st.success(f"✅ Found **{len(df)}** companies")

        # ===== Card UI =====
        for _, row in df.iterrows():
            with st.container():
                st.markdown(f"### 🏢 {row['Company']}")
                st.markdown(f"**👤 {row['Entrepreneur']}** — *{row['Role']}*")
                st.markdown(f"📰 {row['Description']}")
                st.markdown(f"📅 {row['Published']} | 🏷️ {row['Source']}")
                st.markdown(f"[🔗 Read Article]({row['Link']})")
                st.divider()

        csv = df.drop(columns=["Priority"]).to_csv(index=False).encode('utf-8')

        st.download_button(
            "📥 Download CSV",
            csv,
            "entrepreneur_results.csv",
            "text/csv"
        )

    else:
        st.error("No results found. Try increasing lookback or adding sources.")

st.divider()
st.caption("Now supports 12-month discovery across multiple startup news sources")
