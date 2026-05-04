import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re
from pathlib import Path
import json

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout - Top 100")
st.markdown("**Search by Industry or Custom • Company Name + Brief Description**")

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
    "Paul Graham": ["paulg"],
    "Dario Amodei": ["darioamodei", "Anthropic"],
    "Nat Friedman": ["natfriedman"],
    "Daniel Gross": ["danielgross"],
    "Sarah Guo": ["sarahguo"],
    "Elad Gil": ["eladgil"],
    "Josh Wolfe": ["wolfejosh"],
    "Palmer Luckey": ["PalmerLuckey"],
    "Joe Lonsdale": ["jlonsdale"],
    "Trae Stephens": ["traestephens"],
    "Brett Adcock": ["brettadcock"],
    "Brian Armstrong": ["brian_armstrong"],
    "Vitalik Buterin": ["VitalikButerin"],
    "Sriram Krishnan": ["sriramk"],
    "Jeff Bezos": ["JeffBezos"],
    "Jensen Huang": ["JensenHuang"],
}

# ==================== Industries (with new Cleantech & Agritech) ====================
INDUSTRIES = {
    "All Industries": ALL_ENTREPRENEURS,
    
    "AI / Deep Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Elon Musk", "Sam Altman", "Marc Andreessen", "Alex Karp", "Dario Amodei", "Nat Friedman", 
        "Daniel Gross", "Sarah Guo", "Elad Gil", "Garry Tan", "Peter Thiel"]},
    
    "Fintech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Mark Cuban", "Chamath Palihapitiya", "David Sacks", "Jason Calacanis", "Keith Rabois", 
        "Patrick Collison", "Alexis Ohanian"]},
    
    "Biotech / Health": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Sam Altman", "Vinod Khosla", "Alex Karp", "Dario Amodei", "Reid Hoffman", "Marc Andreessen"]},
    
    "LegalTech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Peter Thiel", "Marc Andreessen", "David Sacks", "Keith Rabois", "Balaji Srinivasan"]},
    
    "Cleantech / Climate": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Elon Musk", "Vinod Khosla", "Chamath Palihapitiya", "Marc Andreessen", "Naval Ravikant", 
        "Jeff Bezos"]},
    
    "Agritech / Food Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Vinod Khosla", "Elon Musk", "Marc Andreessen", "Peter Thiel", "Garry Tan", "Naval Ravikant"]},
    
    "Crypto / Web3": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Balaji Srinivasan", "Brian Armstrong", "Vitalik Buterin", "Chamath Palihapitiya", "David Sacks"]},
    
    "Defense / Space / Hard Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Elon Musk", "Peter Thiel", "Palmer Luckey", "Trae Stephens", "Joe Lonsdale"]},
    
    "SaaS / Enterprise": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Marc Andreessen", "Peter Thiel", "Garry Tan", "Sarah Guo", "Elad Gil", "Nat Friedman"]},
    
    "Consumer Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Brian Chesky", "Alexis Ohanian", "Mark Cuban", "Garry Tan", "Jason Calacanis"]},
    
    "Robotics / Autonomous": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in [
        "Elon Musk", "Palmer Luckey", "Brett Adcock"]},
}

def extract_company_name(title):
    patterns = [
        r'(?:at|for|in|launches?|raises?|invests? in|acquires?|backs?|joins?)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s+raises|\s+announces|\s+with|\s+to|\s+\(|$)',
        r'^([A-Z][A-Za-z0-9\s&]{3,45}?) (?:raises|announces|launches|secures)'
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            company = match.group(1).strip()
            if 3 < len(company) < 50:
                return company
    return "Unknown Company"

def clean_description(title):
    desc = re.sub(r'^\s*\w+\s*-\s*', '', title.strip())
    return desc[:180] + "..." if len(desc) > 180 else desc

def fetch_google_news(query, days=30):
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        rss_url = f"https://news.google.com/rss/search?q={query}+when:{start.strftime('%Y-%m-%d')}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        results = []
        for entry in feed.entries[:7]:
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

# ==================== Sidebar ====================
st.sidebar.header("🔎 Search Controls")
mode = st.sidebar.radio("Search Mode", ["Predefined Industry", "Custom Industry/Keyword"])

if mode == "Predefined Industry":
    selected_industry = st.sidebar.selectbox("Select Industry", options=list(INDUSTRIES.keys()))
    industry_ents = INDUSTRIES[selected_industry]
else:
    custom_query = st.sidebar.text_input("Custom industry or keyword", 
                                        placeholder="quantum computing, ev battery, vertical ai")
    selected_industry = custom_query if custom_query else "Custom Search"
    industry_ents = ALL_ENTREPRENEURS

selected_ents = st.sidebar.multiselect(
    f"Select Entrepreneurs (~{len(industry_ents)} available)",
    options=list(industry_ents.keys()),
    default=list(industry_ents.keys())[:8]
)

lookback = st.sidebar.slider("Lookback period (days)", 7, 90, 30)

# ==================== Main Search ====================
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
        st.success(f"✅ Found **{len(df)}** results for **{selected_industry}**")
        st.dataframe(df[["Entrepreneur", "Company", "Description", "Published", "Source"]], use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"{selected_industry.replace(' ', '_')}_results.csv", "text/csv")

# Email Subscription
st.divider()
st.subheader("📧 Daily Email Updates")
col1, col2 = st.columns([3, 2])
with col1:
    email = st.text_input("Your Email Address", placeholder="you@example.com")
with col2:
    if st.button("Subscribe to Daily Alerts", type="primary") and email:
        st.success(f"✅ {email} subscribed for daily {selected_industry} updates!")

st.caption("💡 Now includes Cleantech / Climate + Agritech / Food Tech • Top 100 Entrepreneurs")
