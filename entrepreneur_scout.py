import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re
from pathlib import Path

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout - Top 100")
st.markdown("**TechCrunch + Crunchbase Search**")

# ==================== Entrepreneurs ====================
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
    "Vinod Khosla": ["vkhosla"],
    "Dario Amodei": ["darioamodei", "Anthropic"],
    "Jensen Huang": ["JensenHuang"],
    "Jeff Bezos": ["JeffBezos"],
}

INDUSTRIES = {
    "All Industries": ALL_ENTREPRENEURS,
    "AI / Deep Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Elon Musk", "Sam Altman", "Marc Andreessen", "Alex Karp", "Dario Amodei"]},
    "Fintech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Mark Cuban", "Chamath Palihapitiya", "David Sacks", "Patrick Collison"]},
    "Biotech / Health": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Sam Altman", "Vinod Khosla", "Dario Amodei"]},
    "Cleantech / Climate": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Elon Musk", "Vinod Khosla", "Jeff Bezos"]},
    "Agritech / Food Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Vinod Khosla", "Elon Musk"]},
    "LegalTech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Peter Thiel", "Marc Andreessen", "David Sacks"]},
    "Crypto / Web3": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Balaji Srinivasan", "Chamath Palihapitiya"]},
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

# ==================== Fetch Function with Source Options ====================
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
        for entry in feed.entries[:10]:
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
mode = st.sidebar.radio("Search Mode", ["Predefined Industry", "Custom Industry/Keyword"])

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

lookback = st.sidebar.slider("Lookback period (days)", 7, 90, 14)

if st.button(f"🔍 Search {selected_industry} ({source_option})", type="primary"):
    all_results = []
    progress_bar = st.progress(0)
    
    for idx, name in enumerate(selected_ents):
        st.subheader(f"🔹 {name}")
        terms = industry_ents[name]
        
        for term in terms:
            with st.spinner(f"Searching {term}..."):
                search_term = term if mode == "Predefined Industry" else f"{term} {custom_query}"
                news = fetch_google_news(search_term, lookback, source_filter)
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
        st.success(f"✅ Found **{len(df)}** results with company mentions")
        st.dataframe(df[["Entrepreneur", "Company", "Description", "Published", "Source"]], use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"{selected_industry}_results.csv", "text/csv")
    else:
        st.warning("No results with company mentions found. Try different source or longer period.")

st.divider()
st.caption("💡 Use **Crunchbase Only** for funding & company data • **TechCrunch Only** for startup news")
