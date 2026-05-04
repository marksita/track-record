import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re
from pathlib import Path

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")
st.markdown("**Find Activity from Any Successful Entrepreneurs**")

# ==================== Core Entrepreneurs (used for targeted search) ====================
ALL_ENTREPRENEURS = {
    "Elon Musk": ["elonmusk", "xAI", "Tesla", "SpaceX", "Neuralink"],
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
    # Add more if you want
}

# ==================== Company Detection ====================
KNOWN_COMPANIES = {"tesla", "spacex", "xai", "neuralink", "openai", "anthropic", "stripe", 
                   "airbnb", "palantir", "founders fund", "y combinator", "a16z"}

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
        r'([A-Z][A-Za-z0-9\s&\'\.-]{4,45}?)\s+(?:raises|secures|announces|launches|unveils)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            company = match.group(1).strip()
            if len(company) >= 4 and company.lower() not in ['elon','sam','mark','chamath','david','peter']:
                return company.title()
    return None

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
                "Entrepreneur": name,
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
    "Targeted Search (Specific People)"
])

source_option = st.sidebar.selectbox(
    "News Source", 
    options=["All Sources", "TechCrunch Only", "Crunchbase Only"], 
    index=0
)

source_filter = None
if source_option == "TechCrunch Only":
    source_filter = "techcrunch"
elif source_option == "Crunchbase Only":
    source_filter = "crunchbase"

lookback = st.sidebar.slider("Lookback period (days)", 7, 90, 14)

if search_mode == "Broad Discovery - Any Successful Entrepreneurs":
    if st.button("🚀 Search Recent Activity from Successful Entrepreneurs", type="primary"):
        broad_terms = ["raises $", "secures funding", "new startup", "led investment", "acquires", 
                      "venture capital", "seed round", "Series A", "Series B"]
        
        all_results = []
        seen = set()
        progress_bar = st.progress(0)
        
        for idx, term in enumerate(broad_terms):
            st.subheader(f"Searching: {term}")
            news = fetch_google_news(term, lookback, source_filter)
            
            for item in news:
                # Try to detect entrepreneur from title
                detected_entrepreneur = "Various Entrepreneurs"
                for ent in ALL_ENTREPRENEURS.keys():
                    if ent.lower() in item['Description'].lower():
                        detected_entrepreneur = ent
                        break
                
                key = (detected_entrepreneur, item['Company'].lower())
                if key not in seen:
                    seen.add(key)
                    all_results.append({**item, "Entrepreneur": detected_entrepreneur})
            
            progress_bar.progress((idx + 1) / len(broad_terms))
        
        if all_results:
            df = pd.DataFrame(all_results[:100])
            st.success(f"✅ Found **{len(df)}** recent company activities by successful entrepreneurs")
            st.dataframe(df[["Entrepreneur", "Company", "Description", "Published", "Source"]], use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, "successful_entrepreneurs_results.csv", "text/csv")
        else:
            st.warning("No strong results found. Try increasing lookback days.")

else:
    # Targeted Search (original mode)
    st.info("Use the Broad Discovery mode above to find any successful entrepreneurs dynamically.")

st.divider()
st.caption("💡 Broad Discovery mode searches high-signal funding & startup keywords")
