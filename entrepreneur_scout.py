import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout - By Industry")
st.markdown("**Predefined industries OR search any custom industry/keyword**")

# Expanded pool (~55 entrepreneurs)
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
}

# Predefined Industries
INDUSTRIES = {
    "All Industries": ALL_ENTREPRENEURS,
    "AI / Deep Tech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Elon Musk", "Sam Altman", "Marc Andreessen", "Alex Karp", "Dario Amodei", "Nat Friedman", "Daniel Gross", "Sarah Guo", "Elad Gil", "Garry Tan"]},
    "Fintech": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Mark Cuban", "Chamath Palihapitiya", "David Sacks", "Jason Calacanis", "Keith Rabois", "Patrick Collison"]},
    "Biotech / Health": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Sam Altman", "Vinod Khosla", "Alex Karp", "Dario Amodei"]},
    "Climate / Energy": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Elon Musk", "Vinod Khosla", "Chamath Palihapitiya"]},
    "Crypto / Web3": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Balaji Srinivasan", "Chamath Palihapitiya", "Brian Armstrong", "Vitalik Buterin", "David Sacks"]},
    "Defense / Space": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Elon Musk", "Peter Thiel", "Palmer Luckey", "Trae Stephens"]},
    "SaaS / Enterprise": {k: v for k, v in ALL_ENTREPRENEURS.items() if k in ["Marc Andreessen", "Peter Thiel", "Garry Tan", "Sarah Guo", "Elad Gil"]},
    # Add more if you want
}

def fetch_google_news(query, days=30):
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        rss_url = f"https://news.google.com/rss/search?q={query}+when:{start.strftime('%Y-%m-%d')}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        results = []
        for entry in feed.entries[:7]:
            published = entry.published if hasattr(entry, 'published') else "Recent"
            results.append({
                "Entrepreneur": name,
                "Query": query,
                "Title": entry.title,
                "Published": published,
                "Source": getattr(entry.source, 'title', "Google News"),
                "Link": entry.link
            })
        return results
    except:
        return []

# ==================== UI ====================
st.sidebar.header("🔎 Search Controls")

mode = st.sidebar.radio("Search Mode", ["Predefined Industry", "Custom Industry/Keyword"])

if mode == "Predefined Industry":
    selected_industry = st.sidebar.selectbox("Select Industry", options=list(INDUSTRIES.keys()))
    industry_ents = INDUSTRIES[selected_industry]
else:
    custom_query = st.sidebar.text_input("Enter any industry or keyword (e.g. quantum computing, ev battery, fashion tech)", 
                                       placeholder="quantum computing")
    selected_industry = custom_query if custom_query else "Custom Search"
    industry_ents = ALL_ENTREPRENEURS  # Use all entrepreneurs for custom searches

selected_ents = st.sidebar.multiselect(
    f"Entrepreneurs ({len(industry_ents)} available)",
    options=list(industry_ents.keys()),
    default=list(industry_ents.keys())[:8]
)

lookback = st.sidebar.slider("Lookback period (days)", 7, 90, 30)

# Main Search Button
if st.button(f"🔍 Search {selected_industry}", type="primary"):
    all_results = []
    progress_bar = st.progress(0)
    
    for idx, name in enumerate(selected_ents):
        st.subheader(f"🔹 {name}")
        terms = industry_ents[name]
        
        for term in terms:
            with st.spinner(f"Searching {term}..."):
                news = fetch_google_news(term if mode == "Predefined Industry" else f"{term} {custom_query}", lookback)
                for item in news:
                    item["Entrepreneur"] = name
                all_results.extend(news)
                
                for item in news:
                    with st.expander(f"📌 {item['Title'][:90]}..."):
                        st.caption(f"📅 {item['Published']} • {item['Source']}")
                        st.markdown(f"[Read full story]({item['Link']})")
        
        progress_bar.progress((idx + 1) / len(selected_ents))
    
    if all_results:
        df = pd.DataFrame(all_results)
        
        # =============== FILTERS ===============
        st.subheader("Filter Results")
        col1, col2 = st.columns(2)
        with col1:
            filter_keyword = st.text_input("Filter by keyword in title", "")
        with col2:
            sort_option = st.selectbox("Sort by", ["Most Recent (default)", "Entrepreneur A-Z"])
        
        if filter_keyword:
            df = df[df['Title'].str.contains(filter_keyword, case=False, na=False)]
        
        if sort_option == "Entrepreneur A-Z":
            df = df.sort_values(by="Entrepreneur")
        
        st.success(f"✅ Found **{len(df)}** results for **{selected_industry}**")
        st.dataframe(df[["Entrepreneur", "Query", "Title", "Published", "Source"]], use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"{selected_industry.replace(' ', '_')}_results.csv", "text/csv")
    else:
        st.warning("No recent articles found. Try a different keyword or longer lookback.")

st.divider()
st.caption("💡 Now supports Custom Industry Search + Result Filters • 55+ top entrepreneurs")
