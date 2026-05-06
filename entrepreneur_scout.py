import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# =============================
# SETTINGS
# =============================
MAX_ARTICLES = 40

# =============================
# CLEANING
# =============================

STOPWORDS = {
    "week","wind","supply","legal","group","company",
    "startup","firm","business","tech","data","ai"
}

def clean_company(name):
    name = name.strip()
    if name.lower() in STOPWORDS:
        return None
    if len(name) < 3:
        return None
    return name

# =============================
# PATTERN EXTRACTION (FIXED)
# =============================

def extract_patterns(text):
    results = []

    # 1. X-backed startup Y  ✅ (FIX)
    matches = re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+)-backed.*?(?:startup|company)\s+([A-Z][A-Za-z0-9&\-\.\']+)',
        text
    )
    for person, company in matches:
        company = clean_company(company)
        if company:
            results.append({
                "entrepreneur": person,
                "company": company,
                "role": "Investor"
            })

    # 2. startup Y backed by X
    matches = re.findall(
        r'(?:startup|company)\s+([A-Z][A-Za-z0-9&\-\.\']+).*?backed by.*?([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    )
    for company, person in matches:
        company = clean_company(company)
        if company:
            results.append({
                "entrepreneur": person,
                "company": company,
                "role": "Investor"
            })

    # 3. Y raised funding led by X
    matches = re.findall(
        r'([A-Z][A-Za-z0-9&\-\.\']+).*?(raised|funding).*?(led by|from).*?([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    )
    for company, _, _, person in matches:
        company = clean_company(company)
        if company:
            results.append({
                "entrepreneur": person,
                "company": company,
                "role": "Investor"
            })

    # 4. X founded Y
    matches = re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(founded|co-founded|launched|started).*?([A-Z][A-Za-z0-9&\-\.\']+)',
        text
    )
    for person, _, company in matches:
        company = clean_company(company)
        if company:
            results.append({
                "entrepreneur": person,
                "company": company,
                "role": "Founder"
            })

    return results

# =============================
# SCRAPER
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=4)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:600]
    except:
        return ""

# =============================
# GOOGLE
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:25]

def fetch_all(queries, months):
    results = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_google, q, months) for q in queries]
        for f in futures:
            results.extend(f.result())
    return results

# =============================
# UI
# =============================

st.set_page_config(page_title="Track Record", layout="wide")

st.title("📊 Track Record")
st.markdown("**Find when successful entrepreneurs start or invest in a new company**")

months = st.sidebar.slider("Lookback (months)",1,12,12)

# =============================
# RUN
# =============================

if st.button("🔍 Search"):

    queries = [
        "startup raises funding",
        "startup backed by",
        "founded startup",
        "co-founded startup",
        "invested in startup",
        "led funding round"
    ]

    entries = fetch_all(queries, months)

    results = {}

    for e in entries:

        title = e.title.split(" - ")[0]
        text = title

        # only scrape strong titles
        if any(k in title.lower() for k in ["raised","founded","backed","invested"]):
            text += ". " + fetch_text(e.link)

        events = extract_patterns(text)

        for ev in events:

            person = ev["entrepreneur"]
            company = ev["company"]

            if not person or not company:
                continue

            key = (person, company)

            if key not in results:
                results[key] = {
                    "Entrepreneur": person,
                    "Company": company,
                    "Role": ev["role"],
                    "Title": title,
                    "Link": e.link
                }

    # =============================
    # OUTPUT
    # =============================

    if results:

        df = pd.DataFrame(results.values())

        st.success(f"✅ Found {len(df)} entrepreneur events")

        for _, r in df.iterrows():

            st.markdown(f"### 👤 {r['Entrepreneur']}")
            st.markdown(f"**{r['Role']} → 🏢 {r['Company']}**")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")

            st.divider()

    else:
        st.warning("No entrepreneur activity found")
