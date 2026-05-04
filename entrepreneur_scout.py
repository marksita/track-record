import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re
from pathlib import Path

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")
st.markdown("**Revised Broad Search Algorithm**")

# ==================== Core Successful Entrepreneurs ====================
ALL_ENTREPRENEURS = {
    "Elon Musk": ["elonmusk", "xAI", "Tesla", "SpaceX"],
    "Sam Altman": ["sama", "OpenAI"],
    "Marc Andreessen": ["pmarca", "a16z"],
    "Peter Thiel": ["peterthiel", "Founders Fund"],
    "Garry Tan": ["garrytan", "Y Combinator"],
    "Mark Cuban": ["mcuban"],
    "David Sacks": ["DavidSacks"],
    "Chamath Palihapitiya": ["chamath"],
    "Alex Karp": ["palantir"],
    "Patrick Collison": ["patrickc", "Stripe"],
    "Vinod Khosla": ["vkhosla"],
    "Dario Amodei": ["darioamodei", "Anthropic"],
    "Jason Calacanis": ["jason"],
    "Keith Rabois": ["rabois"],
    "Reid Hoffman": ["reidhoffman"],
}

# ==================== Company Detection ====================
KNOWN_COMPANIES = {"tesla", "spacex", "xai", "neuralink", "openai", "anthropic", "stripe", "airbnb", "palantir"}

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
            orig = re.search(r'(?i)\b' + re.escape(company) + r'\b', title)
            return orig.group(0) if orig else company.title()
    
    patterns = [
        r'(?:invests? in|backs?|acquires?|leads?)\s+([A-Z][A-Za-z0-9\s&\'\.-]{4,45}?)',
        r'([A-Z][A-Za-z0-9\s&\'\.-]{4,45}?)\s+(?:raises|secures|announces|launches|unveils|debuts)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            company = match.group(1).strip()
            if len(company) >= 4 and company.lower() not in ['elon','sam','mark','chamath','david','peter','reid']:
                return company.title()
    return None

def detect_entrepreneur(title, description):
    text = (title + " " + description).lower()
    for ent in ALL_ENTREPRENEURS.keys():
        if ent.lower() in text or any(handle.lower() in text for handle in ALL_ENTREPRENEURS[ent]):
            return ent
    return "Various Successful Entrepreneurs"

def clean_description(title):
    desc = clean_google_title(title)
    return desc[:220] + "..." if len(desc) > 220 else desc

def fetch_google_news(query, days=30, source_filter=None):
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        base_query = query
        if source_filter == "techcrunch":
            base_query += " site:techcrunch.com"
        elif source_filter == "crunchbase":
            base_query += " site:crunchbase.com"
        
        rss_url = f"https://news.google.com/rss/search?q={base_query}+when:{start.strftime('%Y-%m-%d')}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
        results = []
        for entry in feed.entries[:15]:
            title = entry.title or ""
            company = extract_company_name(title)
            if company is None:
                continue
            results.append({
                "Title": title,
                "Company": company,
                "Description": clean_description(title),
                "Published": entry.published if hasattr(entry, 'published') else "Recent",
                "Source": getattr(entry.source, 'title', source_filter.capitalize() if source_filter else "Google News"),
                "Link": entry.link
            })
        return results
    except:
        return []

# ==================== UI ====================
st.sidebar.header("🔎 Search Controls")

search_mode = st.sidebar.radio("Search Mode", [
    "Broad Discovery - Any Successful Entrepreneurs",
    "Targeted Search"
])

source_option = st.sidebar.selectbox("News Source", 
    options=["All Sources", "TechCrunch Only", "Crunchbase Only"], index=0)

source_filter = None
if source_option == "TechCrunch Only": source_filter = "techcrunch"
elif source_option == "Crunchbase Only": source_filter = "crunchbase"

lookback = st.sidebar.slider("Lookback period (days)", 7, 90, 14)

if search_mode == "Broad Discovery - Any Successful Entrepreneurs":
    if st.button("🚀 Run Broad Search - Any Successful Entrepreneurs", type="primary"):
        # Revised Stronger Algorithm
        high_signal_queries = [
            "raises Series A OR Series B OR seed round",
            "new funding OR secures funding",
            "venture capital investment",
            "led investment OR leads investment",
            "acquires startup",
            "launches new startup",
            "Y Combinator batch",
        ]
        
        all_results = []
        seen = set()
        progress_bar = st.progress(0)
        
        for idx, query in enumerate(high_signal_queries):
            st.subheader(f"Searching: {query}")
            news = fetch_google_news(query, lookback, source_filter)
            
            for item in news:
                entrepreneur = detect_entrepreneur(item['Title'], item['Description'])
                key = (entrepreneur, item['Company'].lower())
                
                if key not in seen:
                    seen.add(key)
                    all_results.append({
                        "Entrepreneur": entrepreneur,
                        "Company": item['Company'],
                        "Description": item['Description'],
                        "Published": item['Published'],
                        "Source": item['Source'],
                        "Link": item['Link']
                    })
            
            progress_bar.progress((idx + 1) / len(high_signal_queries))
        
        if all_results:
            df = pd.DataFrame(all_results[:120])  # Cap at 120 for performance
            st.success(f"✅ Found **{len(df)}** high-quality results from successful entrepreneurs")
            st.dataframe(df[["Entrepreneur", "Company", "Description", "Published", "Source"]], use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "broad_successful_entrepreneurs.csv", "text/csv")
        else:
            st.warning("No strong results found. Try increasing the lookback period.")

else:
    st.info("Use **Broad Discovery** mode above for best results.")

st.divider()
st.caption("💡 Revised algorithm uses high-signal funding keywords + better entrepreneur detection")
