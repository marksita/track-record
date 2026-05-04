import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re
from pathlib import Path
import json

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout - Top 100")
st.markdown("**Improved Company Detection • Search by Industry or Custom**")

# ==================== Top ~100 Entrepreneurs ====================
ALL_ENTREPRENEURS = {
    "Elon Musk": ["elonmusk", "xAI", "Tesla", "SpaceX", "Neuralink"],
    "Sam Altman": ["sama", "OpenAI"],
    "Marc Andreessen": ["pmarca", "a16z"],
    "Peter Thiel": ["peterthiel", "Founders Fund"],
    "Garry Tan": ["garrytan", "Y Combinator"],
    "Mark Cuban": ["mcuban"],
    "Naval Ravikant": ["naval"],
    "Balaji Srinivasan": ["balajis"],
    "Reid Hoffman": ["reidhoffman"],
    "Chamath Palihapitiya": ["chamath"],
    "David Sacks": ["DavidSacks"],
    "Jason Calacanis": ["jason"],
    "Keith Rabois": ["rabois"],
    "Alex Karp": ["palantir"],
    "Patrick Collison": ["patrickc", "Stripe"],
    "Brian Chesky": ["bchesky", "Airbnb"],
    "Alexis Ohanian": ["alexisohanian"],
    "Vinod Khosla": ["vkhosla"],
    "Dario Amodei": ["darioamodei", "Anthropic"],
    "Jensen Huang": ["JensenHuang"],
    "Jeff Bezos": ["JeffBezos"],
    # ... (you can keep the full list from previous version)
}

# ==================== Industries (with Cleantech & Agritech) ====================
INDUSTRIES = {
    "All Industries": ALL_ENTREPRENEURS,
    "AI / Deep Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Elon Musk", "Sam Altman", "Marc Andreessen", "Alex Karp", "Dario Amodei"]},
    "Fintech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Mark Cuban", "Chamath Palihapitiya", "David Sacks", "Patrick Collison"]},
    "Biotech / Health": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Sam Altman", "Vinod Khosla", "Dario Amodei"]},
    "Cleantech / Climate": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Elon Musk", "Vinod Khosla", "Jeff Bezos"]},
    "Agritech / Food Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Vinod Khosla", "Elon Musk"]},
    "LegalTech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Peter Thiel", "Marc Andreessen", "David Sacks"]},
    # ... add other industries as needed
}

# ==================== IMPROVED Company Name Extraction ====================
def extract_company_name(title):
    if not title:
        return "Unknown Company"
    
    # Much better patterns
    patterns = [
        # Common funding/investment patterns
        r'(?:invests? in|leads?|backs?|acquires?|joins?|launches? at)\s+([A-Z][A-Za-z0-9\s&\'-]+?)(?:\s+raises|\s+announces|\s+to|\s+\(|$)',
        r'([A-Z][A-Za-z0-9\s&\'-]+?)\s+(?:raises|secures|announces|launches|gets|unveils)',
        # Direct company at start
        r'^([A-Z][A-Za-z0-9\s&\'-]+?)(?:\s+raises|\s+announces|\s+unveils|\s+launches)',
        # After "from", "by", etc.
        r'(?:from|by|at)\s+([A-Z][A-Za-z0-9\s&\'-]+?)(?:\s|$)',
    ]
    
    title = title.strip()
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            # Clean up common noise
            company = re.sub(r'\s+(?:Inc|LLC|Corp|Ltd| plc)$', '', company, flags=re.IGNORECASE)
            if len(company) >= 3 and len(company) <= 45 and not company.islower():
                return company
    
    return "Unknown Company"

def clean_description(title):
    desc = re.sub(r'^\s*\w+\s*-\s*', '', title.strip())
    return desc[:200] + "..." if len(desc) > 200 else desc

def fetch_google_news(query, days=30):
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        rss_url = f"https://news.google.com/rss/search?q={query}+when:{start.strftime('%Y-%m-%d')}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        results = []
        for entry in feed.entries[:8]:
            title = entry.title
            company = extract_company_name(title)
            
            results.append({
                "Entrepreneur": name,
                "Company": company,
                "Description": clean_description(title),
                "Published": entry.published if hasattr(entry, 'published') else "Recent",
                "Source": getattr(entry.source, 'title', "Google News"),
                "Link": entry.link
            })
        return results
    except:
        return []

# ==================== Sidebar & Search (same as before) ====================
st.sidebar.header("🔎 Search Controls")
mode = st.sidebar.radio("Search Mode", ["Predefined Industry", "Custom Industry/Keyword"])

if mode == "Predefined Industry":
    selected_industry = st.sidebar.selectbox("Select Industry", options=list(INDUSTRIES.keys()))
    industry_ents = INDUSTRIES[selected_industry]
else:
    custom_query = st.sidebar.text_input("Custom industry or keyword", placeholder="quantum computing, ev battery...")
    selected_industry = custom_query if custom_query else "Custom Search"
    industry_ents = ALL_ENTREPRENEURS

selected_ents = st.sidebar.multiselect(
    f"Select Entrepreneurs (~{len(industry_ents)} available)",
    options=list(industry_ents.keys()),
    default=list(industry_ents.keys())[:8]
)

lookback = st.sidebar.slider("Lookback period (days)", 7, 90, 30)

# Main Search
if st.button(f"🔍 Search {selected_industry}", type="primary"):
    all_results = []
    progress_bar = st.progress(0)
    
    for idx, name in enumerate(selected_ents):
        st.subheader(f"🔹 {name}")
        terms = industry_ents[name]
        
        for term in terms:
            with st.spinner(f"Searching {term}..."):
                search_term = term if mode == "Predefined Industry" else f"{term} {custom_query}"
                news = fetch_google_news(search_term, lookback)
                
                for item in news:
                    item["Entrepreneur"] = name
                all_results.extend(news)
                
                for item in news:
                    with st.expander(f"🏢 {item['Company']}"):
                        st.caption(f"📅 {item['Published']} • {item['Source']}")
                        st.markdown(f"**Company:** {item['Company']}")
                        st.write(item['Description'])
                        st.markdown(f"[🔗 Read Full Article]({item['Link']})")
        
        progress_bar.progress((idx + 1) / len(selected_ents))
    
    if all_results:
        df = pd.DataFrame(all_results)
        st.success(f"✅ Found **{len(df)}** results")
        st.dataframe(df[["Entrepreneur", "Company", "Description", "Published", "Source"]], use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"{selected_industry}_results.csv", "text/csv")

st.caption("💡 Improved Company Name Detection • Cleantech + Agritech Included")
