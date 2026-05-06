import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

MAX_ARTICLES = 60

# =============================
# FILTERS
# =============================

STOPWORDS = {
    "week","wind","supply","legal","group","company",
    "startup","firm","business","tech","data","ai"
}

INVALID_ENTITIES = {
    "partners","capital","ventures","vc","fund","investors"
}

def clean_company(name):
    if not name:
        return None
    if name.lower() in STOPWORDS:
        return None
    if len(name) < 2:
        return None
    return name.strip()

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

def is_company_like(name):
    return any(w in name.lower() for w in INVALID_ENTITIES)

# =============================
# COMPANY EXTRACTION (FIXED)
# =============================

def extract_company(text):

    # 1. "startup Lifeforce"
    m = re.search(
        r'(?:startup|company)\s+([A-Z][A-Za-z0-9&\-\.\']+)',
        text
    )
    if m:
        company = clean_company(m.group(1))
        if company and not is_valid_person(company):
            return company

    # 2. "Lifeforce, a startup"
    m = re.search(
        r'([A-Z][A-Za-z0-9&\-\.\']+),?\s+(?:a|an)\s+(?:\w+\s)?startup',
        text
    )
    if m:
        company = clean_company(m.group(1))
        if company and not is_valid_person(company):
            return company

    # 3. first word fallback (title start)
    m = re.match(r'^([A-Z][A-Za-z0-9&\-\.\']+)', text)
    if m:
        company = clean_company(m.group(1))
        if company and not is_valid_person(company):
            return company

    return None

# =============================
# PATTERN EXTRACTION
# =============================

def extract_patterns(text):

    results = []
    company = extract_company(text)

    if not company:
        return results

    # founders list
    matches = re.findall(
        r'founded by ([A-Z][a-z]+ [A-Z][a-z]+(?:, [A-Z][a-z]+ [A-Z][a-z]+)*)',
        text
    )
    for group in matches:
        people = re.findall(r'[A-Z][a-z]+ [A-Z][a-z]+', group)
        for p in people:
            if is_valid_person(p):
                results.append((p, company, "Founder"))

    # single founder mention
    matches = re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?founded',
        text
    )
    for p in matches:
        if is_valid_person(p):
            results.append((p, company, "Founder"))

    # backed by
    matches = re.findall(
        r'backed by ([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    )
    for p in matches:
        if is_valid_person(p) and not is_company_like(p):
            results.append((p, company, "Investor"))

    # led by
    matches = re.findall(
        r'led by ([A-Z][a-z]+ [A-Z][a-z]+)',
        text
    )
    for p in matches:
        if is_valid_person(p) and not is_company_like(p):
            results.append((p, company, "Investor"))

    # invests in
    matches = re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(invested in|backs).*?',
        text
    )
    for p, _ in matches:
        if is_valid_person(p):
            results.append((p, company, "Investor"))

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
        "startup backed by",
        "founded startup",
        "co-founded startup",
        "invested in startup",
        "led funding round",
        "startup secures funding"
    ]

    entries = fetch_all(queries, months)

    company_results = {}

    for e in entries:

        title = e.title.split(" - ")[0]
        text = title

        if any(k in title.lower() for k in ["raised","founded","backed","invested","funding"]):
            text += ". " + fetch_text(e.link)

        events = extract_patterns(text)

        for person, company, role in events:

            if not is_valid_person(person):
                continue

            if is_company_like(person):
                continue

            if company not in company_results:
                company_results[company] = {
                    "people": [],
                    "title": title,
                    "link": e.link
                }

            company_results[company]["people"].append((person, role))

    # =============================
    # OUTPUT (GROUPED)
    # =============================

    if company_results:

        st.success(f"Found {len(company_results)} companies")

        for company, data in company_results.items():

            st.markdown(f"### 🏢 {company}")

            for person, role in list(set(data["people"])):
                st.markdown(f"👤 {person} — {role}")

            st.markdown(f"📰 {data['title']}")
            st.markdown(f"[Read Article]({data['link']})")

            st.divider()

    else:
        st.warning("No entrepreneur activity found")
