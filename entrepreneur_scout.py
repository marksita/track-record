import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")
st.markdown("**Broad Discovery - Any Successful Entrepreneurs** (Revised)")

# Core Entrepreneurs for detection
ALL_ENTREPRENEURS = {
    "Elon Musk", "Sam Altman", "Marc Andreessen", "Peter Thiel", "Garry Tan", "Mark Cuban",
    "David Sacks", "Chamath Palihapitiya", "Alex Karp", "Patrick Collison", "Vinod Khosla",
    "Dario Amodei", "Jason Calacanis", "Keith Rabois", "Reid Hoffman"
}

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
    
    # Funding patterns
    patterns = [
        r'([A-Z][A-Za-z0-9\s&\'\.-]{4,45}?)\s+(?:raises|secures|announces|launches|unveils)',
        r'(?:invests? in|backs?|acquires?|leads?)\s+([A-Z][A-Za-z0-9\s&\'\.-]{4,45}?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            company = match.group(1).strip() if len(match.groups()) > 1 else match.group(0).strip()
            if len(company) >= 4 and company.lower() not in ['elon','sam','mark','chamath','david','peter']:
                return company.title()
    return None

def detect_entrepreneur(text):
    text = text.lower()
    for ent in ALL_ENTREPRENEURS:
        if ent.lower() in text:
            return ent
    return "Successful Entrepreneur"

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
        for entry in feed.entries[:12]:
            title = entry.title or ""
            company = extract_company_name(title)
            if company is None:
                continue
            results.append({
                "Company": company,
                "Description": clean_google_title(title),
                "Published": entry.published if hasattr(entry, 'published') else "Recent",
                "Source": getattr(entry.source, 'title', source_filter.capitalize() if source_filter else "Google News"),
                "Link": entry.link
            })
        return results
    except:
        return []

# ==================== UI ====================
st.sidebar.header("Search Controls")

search_mode = st.sidebar.radio("Mode", ["Broad Discovery - Any Successful Entrepreneurs", "Targeted Search"])

source_option = st.sidebar.selectbox("News Source", 
    ["All Sources", "TechCrunch Only", "Crunchbase Only"])

source_filter = None
if source_option == "TechCrunch Only":
    source_filter = "techcrunch"
elif source_option == "Crunchbase Only":
    source_filter = "crunchbase"

lookback = st.sidebar.slider("Lookback (days)", 7, 90, 14)

if search_mode == "Broad Discovery - Any Successful Entrepreneurs":
    if st.button("🚀 Run Broad Search for Successful Entrepreneurs", type="primary"):
        # Simplified, high-performing queries
        queries = [
            "startup raises",
            "secures funding",
            "new funding round",
            "led investment",
            "acquires startup",
            "Y Combinator",
            "venture capital"
        ]
        
        all_results = []
        seen = set()
        progress_bar = st.progress(0)
        
        for idx, q in enumerate(queries):
            with st.spinner(f"Searching '{q}'..."):
                news = fetch_google_news(q, lookback, source_filter)
                
                for item in news:
                    entrepreneur = detect_entrepreneur(item['Description'])
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
            
            progress_bar.progress((idx + 1) / len(queries))
        
        if all_results:
            df = pd.DataFrame(all_results[:100])
            st.success(f"✅ Found **{len(df)}** results")
            st.dataframe(df[["Entrepreneur", "Company", "Description", "Published", "Source"]], use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "broad_entrepreneurs_results.csv", "text/csv")
        else:
            st.error("No results found. Try increasing lookback or switching source.")

else:
    st.info("Targeted search mode coming soon...")

st.divider()
st.caption("Broad Discovery uses simplified high-signal funding keywords for better reliability")
