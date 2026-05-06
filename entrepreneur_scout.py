import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

MAX_ARTICLES = 60

STOPWORDS = {
    "week","wind","supply","legal","group","company",
    "startup","firm","business","tech","data","ai"
}

INVALID_ENTITIES = {
    "partners","capital","ventures","vc","fund","investors"
}

def clean_company(name):
    if name.lower() in STOPWORDS:
        return None
    return name.strip()

def is_valid_person(name):
    parts = name.split()
    return (
        len(parts) == 2
        and all(p[0].isupper() for p in parts)
        and all(p.isalpha() for p in parts)
    )

def is_company_like(name):
    return any(w in name.lower() for w in INVALID_ENTITIES)

# =============================
# EXTRACTION
# =============================

def extract_patterns(text):
    results = []

    # Extract company (multi-word)
    company_match = re.findall(
        r'([A-Z][A-Za-z0-9&\-\.\']+(?:\s[A-Z][A-Za-z0-9&\-\.\']+)*)',
        text
    )
    company = None
    if company_match:
        company = sorted(company_match, key=lambda x: -len(x.split()))[0]
        company = clean_company(company)

    if not company:
        return results

    # 1. founders list
    matches = re.findall(
        r'founded by ([A-Z][a-z]+ [A-Z][a-z]+(?:, [A-Z][a-z]+ [A-Z][a-z]+)*)',
        text
    )
    for group in matches:
        people = re.findall(r'[A-Z][a-z]+ [A-Z][a-z]+', group)
        for p in people:
            if is_valid_person(p):
                results.append((p, company, "Founder"))

    # 2. backed by
    matches = re.findall(
        r'backed by ([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    )
    for person in matches:
        if is_valid_person(person) and not is_company_like(person):
            results.append((person, company, "Investor"))

    # 3. led by
    matches = re.findall(
        r'led by ([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    )
    for person in matches:
        if is_valid_person(person) and not is_company_like(person):
            results.append((person, company, "Investor"))

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
# FEEDS
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
st.markdown("Find when successful entrepreneurs start or invest in a new company")

months = st.sidebar.slider("Lookback (months)",1,12,12)

# =============================
# RUN
# =============================

if st.button("Search"):

    queries = [
        "startup raises funding",
        "founded startup",
        "startup backed by",
        "startup led by founder",
        "startup co-founded"
    ]

    entries = fetch_all(queries, months)

    results = {}

    for e in entries:

        title = e.title.split(" - ")[0]
        text = title

        if any(k in title.lower() for k in ["raised","founded","backed"]):
            text += ". " + fetch_text(e.link)

        events = extract_patterns(text)

        for person, company, role in events:

            if not is_valid_person(person):
                continue

            if is_company_like(person):
                continue

            key = (person, company)

            if key not in results:
                results[key] = {
                    "Company": company,
                    "Entrepreneur": person,
                    "Role": role,
                    "Title": title,
                    "Link": e.link
                }

    # =============================
    # OUTPUT
    # =============================

    if results:

        df = pd.DataFrame(results.values())

        st.success(f"Found {len(df)} results")

        for _, r in df.iterrows():

            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"👤 {r['Entrepreneur']} — {r['Role']}")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"[Read Article]({r['Link']})")
            st.divider()

    else:
        st.warning("No entrepreneur activity found")
