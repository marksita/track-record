import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

MAX_ARTICLES = 50

# =============================
# VALIDATION
# =============================

STOPWORDS = {
    "week","wind","supply","legal","group","company",
    "startup","firm","business","tech","data","ai",
    "one","biggest","round","capital","raises"
}

def clean_company(name):
    name = name.strip()
    if name.lower() in STOPWORDS:
        return None
    if len(name) < 3:
        return None
    return name

def is_valid_person(name):
    parts = name.split()

    if len(parts) != 2:
        return False

    if not all(p[0].isupper() for p in parts):
        return False

    if not all(p.isalpha() for p in parts):
        return False

    if any(p.lower() in STOPWORDS for p in parts):
        return False

    return True

# =============================
# PATTERN EXTRACTION
# =============================

def extract_patterns(text):
    results = []

    # 1. Bill Gates-backed startup AirLoom
    for person, company in re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+)-backed.*?(?:startup|company)?\s*([A-Z][A-Za-z0-9&\-\.\']+)',
        text
    ):
        company = clean_company(company)
        if company and is_valid_person(person):
            results.append((person, company, "Investor"))

    # 2. AirLoom backed by Bill Gates
    for company, person in re.findall(
        r'([A-Z][A-Za-z0-9&\-\.\']+).*?(?:backed|funded|supported).*?by.*?([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    ):
        company = clean_company(company)
        if company and is_valid_person(person):
            results.append((person, company, "Investor"))

    # 3. AirLoom raises funding from Bill Gates
    for company, person in re.findall(
        r'([A-Z][A-Za-z0-9&\-\.\']+).*?(?:raises|raised|secures).*?(?:from|led by).*?([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    ):
        company = clean_company(company)
        if company and is_valid_person(person):
            results.append((person, company, "Investor"))

    # 4. Bill Gates invests in AirLoom
    for person, company in re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(?:invests in|invested in|backs).*?([A-Z][A-Za-z0-9&\-\.\']+)',
        text
    ):
        company = clean_company(company)
        if company and is_valid_person(person):
            results.append((person, company, "Investor"))

    # 5. Bill Gates founded AirLoom
    for person, company in re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(?:founded|co-founded|launched|started).*?([A-Z][A-Za-z0-9&\-\.\']+)',
        text
    ):
        company = clean_company(company)
        if company and is_valid_person(person):
            results.append((person, company, "Founder"))

    return results

# =============================
# SCRAPER
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=4)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:500]
    except:
        return ""

# =============================
# GOOGLE
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:30]

def fetch_all(queries, months):
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
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

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

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
        "led funding round",
        "startup secures funding",
        "startup raises capital"
    ]

    entries = fetch_all(queries, months)

    results = {}

    for e in entries:

        title = e.title.split(" - ")[0]
        text = title

        # scrape only strong signals
        if any(k in title.lower() for k in ["raised","founded","backed","invested","funding"]):
            text += ". " + fetch_text(e.link)

        events = extract_patterns(text)

        for person, company, role in events:

            key = (person, company)

            if key not in results:
                results[key] = {
                    "Entrepreneur": person,
                    "Company": company,
                    "Role": role,
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
