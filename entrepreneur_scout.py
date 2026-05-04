import streamlit as st
import requests
import feedparser
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")
st.markdown("**Free tool to find recent startups & investments by successful entrepreneurs**")

# List of successful entrepreneurs
ENTREPRENEURS = {
    "Elon Musk": ["elonmusk", "xAI", "Tesla", "SpaceX", "Neuralink"],
    "Mark Cuban": ["mcuban"],
    "Peter Thiel": ["peterthiel", "Founders Fund"],
    "Garry Tan": ["garrytan", "Y Combinator"],
    "Paul Graham": ["paulg"],
    "Sam Altman": ["sama", "OpenAI"],
    "Naval Ravikant": ["naval"],
    "Balaji Srinivasan": ["balajis"],
    "Marc Andreessen": ["pmarca", "a16z"],
    "Alex Karp": ["palantir"],
}

def fetch_google_news(query, days=30):
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        rss_url = f"https://news.google.com/rss/search?q={query}+when:{start.strftime('%Y-%m-%d')}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        results = []
        for entry in feed.entries[:8]:
            published = entry.published if hasattr(entry, 'published') else "Recent"
            results.append({
                "Query": query,
                "Title": entry.title,
                "Published": published,
                "Source": entry.source.title if hasattr(entry, 'source') else "Google News",
                "Link": entry.link
            })
        return results
    except:
        return []

# Sidebar
st.sidebar.header("Filters")
selected_ents = st.sidebar.multiselect(
    "Select Entrepreneurs", 
    options=list(ENTREPRENEURS.keys()), 
    default=["Elon Musk", "Mark Cuban", "Garry Tan", "Sam Altman"]
)

lookback = st.sidebar.slider("Lookback period (days)", min_value=7, max_value=90, value=30)

if st.button("🔍 Search Recent Activity", type="primary"):
    all_results = []
    progress_bar = st.progress(0)
    
    for idx, name in enumerate(selected_ents):
        st.subheader(f"🔹 {name}")
        terms = ENTREPRENEURS[name]
        
        for term in terms:
            with st.spinner(f"Searching for {term}..."):
                news = fetch_google_news(term, lookback)
                all_results.extend(news)
                
                for item in news:
                    with st.expander(f"📌 {item['Title'][:100]}..."):
                        st.caption(f"📅 {item['Published']} | Source: {item['Source']}")
                        st.markdown(f"[Read Article]({item['Link']})")
        
        progress_bar.progress((idx + 1) / len(selected_ents))
    
    if all_results:
        df = pd.DataFrame(all_results)
        st.success(f"✅ Found {len(df)} recent mentions!")
        st.dataframe(df[["Query", "Title", "Published", "Source"]], use_container_width=True)
    else:
        st.warning("No recent news found. Try increasing the lookback days.")

st.divider()
st.info("💡 This app uses public Google News RSS. No API keys required.")
