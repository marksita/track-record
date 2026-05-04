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

# ==================== Helpers ====================
def clean_google_title(title):
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title.strip()

def extract_company_name(title):
    if not title:
        return None

    clean_title = clean_google_title(title).lower()

    # Known companies first
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

# ==================== News Fetch ====================
def fetch_google_news(query, days=30, source_filter=None):
    try:
        end = datetime.now()
        start = end - timedelta(days=days)

        base_query = query
        if source_filter == "techcrunch":
            base_query += " site:techcrunch.com"
        elif source_filter == "crunchbase":
            base_query += " site:crunchbase.com"

        encoded_query = urllib.parse.quote_plus(base_query)

        rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:{start.strftime('%Y-%m-%d')}&hl=en-US&gl=US&ceid=US:en"

        feed = feedparser.parse(rss_url)
        results = []

        for entry in feed.entries[:15]:
            title = entry.title or ""
            clean_title = clean_google_title(title)

            company = extract_company_name(title)

            # 🚫 Only keep real companies
            if company is None:
                continue

            entrepreneur, role = extract_entrepreneur_and_action(clean_title)

            results.append({
                "Entrepreneur": entrepreneur,
                "Role": role,
                "Company": company,
                "Description": clean_title,
                "Published": entry.published if hasattr(entry, 'published') else "Recent",
                "Source": getattr(entry.source, 'title', source_filter.capitalize() if source_filter else "Google News"),
                "Link": entry.link
            })

        return results

    except Exception as e:
        st.error(f"Error fetching news: {e}")
        return []

# ==================== UI ====================
st.sidebar.header("Search Controls")

source_option = st.sidebar.selectbox(
    "News Source",
    ["All Sources", "TechCrunch Only", "Crunchbase Only"]
)

source_filter = None
if source_option == "TechCrunch Only":
    source_filter = "techcrunch"
elif source_option == "Crunchbase Only":
    source_filter = "crunchbase"

lookback = st.sidebar.slider("Lookback (days)", 7, 90, 14)

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

    for idx, q in enumerate(queries):
        with st.spinner(f"Searching '{q}'..."):
            news = fetch_google_news(q, lookback, source_filter)

            for item in news:
                key = item["Description"]

                if key not in seen:
                    seen.add(key)
                    all_results.append(item)

        progress_bar.progress((idx + 1) / len(queries))

    if all_results:
        df = pd.DataFrame(all_results)

        # Boost known entrepreneurs
        df["Priority"] = df["Entrepreneur"].apply(lambda x: 1 if is_high_signal(x) else 0)
        df = df.sort_values(by="Priority", ascending=False)

        st.success(f"✅ Found **{len(df)}** companies")

        # ===== Pretty Card UI =====
        for _, row in df.iterrows():
            with st.container():
                st.markdown(f"### 🏢 {row['Company']}")
                st.markdown(f"**👤 {row['Entrepreneur']}** — *{row['Role']}*")
                st.markdown(f"📰 {row['Description']}")
                st.markdown(f"📅 {row['Published']} | 🏷️ {row['Source']}")
                st.markdown(f"[🔗 Read Article]({row['Link']})")
                st.divider()

        # CSV download
        csv = df.drop(columns=["Priority"]).to_csv(index=False).encode('utf-8')

        st.download_button(
            "📥 Download CSV",
            csv,
            "entrepreneur_results.csv",
            "text/csv"
        )

    else:
        st.error("No high-quality company results found. Try increasing lookback.")

st.divider()
st.caption("Filtered for real companies + improved readability")
