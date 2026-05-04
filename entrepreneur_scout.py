import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")

# ==================== SOURCES ====================
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "Crunchbase News": "https://news.crunchbase.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "WIRED": "https://www.wired.com/feed/rss",
    "Forbes Tech": "https://www.forbes.com/technology/feed/",
    "Business Insider": "https://www.businessinsider.com/rss",
    "Tech.eu": "https://tech.eu/feed/",
    "Startup Daily": "https://www.startupdaily.net/feed/",
    "SmartCompany": "https://www.smartcompany.com.au/feed/",
    "InnovationAus": "https://www.innovationaus.com/feed/",
    "AFR": "https://www.afr.com/rss"
}

GOOGLE_SOURCE = "Google News"

# ==================== SCRAPING ====================
@st.cache_data(ttl=3600)
def fetch_article_text(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:3000]
    except:
        return ""

# ==================== FILTERS ====================
def is_relevant(text):
    return any(k in text.lower() for k in [
        "startup", "funding", "raises", "venture",
        "joins", "appointed", "ceo"
    ])

def strong_signal(text):
    return any(k in text.lower() for k in [
        "raises", "funding", "joins", "appointed", "hired"
    ])

def is_roundup(text):
    return any(k in text.lower() for k in [
        "the week", "top deals", "roundup"
    ])

# ==================== EXTRACTION ====================
BLOCK_WORDS = {
    "Startup", "Company", "Tech", "Legal",
    "Week", "Rounds", "Deals",
    "Swedish", "Australian", "American"
}

def is_valid_company(name):
    return name and len(name) >= 3 and name not in BLOCK_WORDS

def extract_company(text):
    patterns = [
        r'([A-Z][A-Za-z0-9&\-\.\']+)\s+(raises|lands|secures)',
        r'(?:joins|joined|appointed)\s+(?:[A-Za-z]+\s+){0,3}?([A-Z][A-Za-z0-9&\-\.\']+)'
    ]

    for p in patterns:
        matches = re.findall(p, text)
        if matches:
            match = matches[-1]
            company = match[0] if isinstance(match, tuple) else match
            if is_valid_company(company):
                return company

    return None

def extract_entrepreneur(text):
    patterns = [
        r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(joins|joined|appointed|hired)',
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(CEO|founder|executive)'
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)

    names = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
    return names[0] if names else None

# ==================== NEW: BACKGROUND DETECTION ====================
def extract_background(text):
    patterns = [
        r'ex[- ]([A-Z][A-Za-z0-9&\-\.\']+)',
        r'former\s+([A-Z][A-Za-z0-9&\-\.\']+)',
        r'previously\s+at\s+([A-Z][A-Za-z0-9&\-\.\']+)'
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(1)

    return None

def detect_role(text):
    t = text.lower()
    if "join" in t or "appointed" in t:
        return "Operator"
    if "invest" in t:
        return "Investor"
    if "found" in t:
        return "Founder"
    return "Mentioned"

# ==================== FETCH ====================
def fetch_google(query, months):
    q = urllib.parse.quote_plus(query + " Australia")
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m&hl=en-AU&gl=AU&ceid=AU:en"
    return feedparser.parse(url).entries[:15]

# ==================== UI ====================
months = st.sidebar.slider("Lookback (months)", 1, 12, 3)

# ==================== MAIN ====================
if st.button("🚀 Run Discovery"):

    queries = [
        "startup raises funding Australia",
        "startup hires CEO",
        "joins startup CEO",
        "former Google joins startup",
        "ex Stripe joins startup"
    ]

    results = []
    seen = set()

    def process(entry, source):
        title = entry.title or ""
        clean = title.split(" - ")[0].strip()

        if clean in seen:
            return
        seen.add(clean)

        article = fetch_article_text(entry.link)
        text = clean + " " + article

        if is_roundup(text):
            return
        if not is_relevant(text):
            return
        if not strong_signal(text):
            return

        company = extract_company(text)
        person = extract_entrepreneur(text)
        background = extract_background(text)

        if not company or not person:
            return

        score = 1
        if background:
            score += 2  # 🔥 boost high-quality operators

        results.append({
            "Entrepreneur": person,
            "Company": company,
            "Background": background or "",
            "Role": detect_role(text),
            "Score": score,
            "Title": clean,
            "Source": source,
            "Link": entry.link
        })

    # Google
    for q in queries:
        for e in fetch_google(q, months):
            process(e, GOOGLE_SOURCE)

    # RSS
    for src, url in RSS_FEEDS.items():
        for e in feedparser.parse(url).entries[:20]:
            process(e, src)

    # ==================== DISPLAY ====================
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']}** — *{r['Role']}*")

            if r["Background"]:
                st.markdown(f"🏆 ex-{r['Background']}")

            st.markdown(f"🔥 Score: {r['Score']}")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"📡 {r['Source']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()

    else:
        st.error("No results found")
