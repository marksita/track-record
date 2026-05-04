import streamlit as st
import feedparser
from datetime import datetime, timedelta
import pandas as pd
import re
from pathlib import Path

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout - Top 100")
st.markdown("**Improved Company Detection v2**")

# (Keep your ALL_ENTREPRENEURS and INDUSTRIES dictionaries from the previous version)

# ==================== STRONGER Company Name Extraction ====================
def clean_google_title(title):
    """Remove source name from the end (e.g. ' - TechCrunch')"""
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    return title.strip(), ""

def extract_company_name(title):
    if not title:
        return "Unknown Company"
    
    clean_title, _ = clean_google_title(title)
    
    patterns = [
        # Most common: "Company raises/funding/launch"
        r'([A-Z][A-Za-z0-9\s&\'\.-]+?)\s+(?:raises|secures|announces|launches|unveils|gets|debuts|introduces)',
        # "invests in / backs / acquires Company"
        r'(?:invests? in|leads?|backs?|acquires?|joins?|partnering with)\s+([A-Z][A-Za-z0-9\s&\'\.-]+?)(?:\s+to|\s+\(|\s+from|$)',
        # Company at the very start
        r'^([A-Z][A-Za-z0-9\s&\'\.-]{4,45}?)(?:\s+raises|\s+announces|\s+launches)',
        # After keywords
        r'(?:from|at|by|with)\s+([A-Z][A-Za-z0-9\s&\'\.-]+?)(?:\s|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_title, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            # Clean common suffixes
            company = re.sub(r'\s+(Inc|LLC|Corp|Ltd|PLC|NV|SA)$', '', company, flags=re.IGNORECASE)
            if len(company) >= 3 and len(company) <= 48:
                return company.title()
    
    # Fallback: Take first capitalized phrase
    fallback = re.search(r'([A-Z][A-Za-z0-9\s&\'\.-]{4,40})', clean_title)
    if fallback:
        candidate = fallback.group(1).strip()
        if len(candidate) >= 4:
            return candidate.title()
    
    return "Unknown Company"

def clean_description(title):
    clean_title, source = clean_google_title(title)
    desc = clean_title
    return desc[:220] + "..." if len(desc) > 220 else desc

# ==================== Fetch Function ====================
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
    except Exception as e:
        st.error(f"Error fetching news: {e}")
        return []

# ==================== Rest of the UI (same as before) ====================
# ... [Keep your sidebar, search logic, expander cards, and email subscription exactly as in the last version]

st.caption("💡 Company Detection Improved v2 • Test with 'AI' or 'Tesla' searches")
