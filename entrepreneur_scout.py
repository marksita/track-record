import streamlit as st
import feedparser
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# =============================
# CONFIG
# =============================

MAX_ARTICLES = 500

# =============================
# FILTERS
# =============================

COMPANY_WORDS = {
    "ai","ml","labs","lab","systems","technologies","tech",
    "intelligence","solutions","platform","robotics",
    "fintech","capital","ventures","group","fund","studios"
}

GENERIC_WORDS = {
    "south","north","east","west","downtown",
    "innovation","social","global","digital"
}

KEYWORDS = [
    "founded","backed","raises","raised",
    "funding","launch","led","investors"
]

# =============================
# PERSON VALIDATION (FIXED)
# =============================

def is_valid_person(name):
    parts = name.split()

    if len(parts) != 2:
        return False

    if not all(p[0].isupper() for p in parts):
        return False

    if not all(p.isalpha() for p in parts):
        return False

    # block company-like words
    if any(p.lower() in COMPANY_WORDS for p in parts):
        return False

    # block location / generic
    if any(p.lower() in GENERIC_WORDS for p in parts):
        return False

    return True

# =============================
# COMPANY EXTRACTION
# =============================

def extract_company(text):

    patterns = [
        r'startup\s+([A-Z][A-Za-z0-9&\-]+)',
        r'([A-Z][A-Za-z0-9&\-]+)\s+(raises|raised|secures)',
        r'([A-Z][A-Za-z0-9&\-]+),?\s+(?:a|an)\s+startup',
        r'launch(?:es|ed)?\s+([A-Z][A-Za-z0-9&\-]+)'
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)

    return None

# =============================
# PERSON EXTRACTION
# =============================

def extract_people(text):
    candidates = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
    return list(set([c for c in candidates if is_valid_person(c)]))

# =============================
# EVENT EXTRACTION
# =============================

def extract_events(text):

    company = extract_company(text)
    if not company:
        return []

    people = extract_people(text)
    results = []

    # founder patterns
    for p in re.findall(r'founded by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in people:
            results.append((p, company, "Founder"))

    for p in re.findall(r'co-founded by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in people:
            results.append((p, company, "Founder"))

    # investor patterns
    for p in re.findall(r'backed by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in people:
            results.append((p, company, "Investor"))

    for p in re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)-backed', text):
        if p in people:
            results.append((p, company, "Investor"))

    for p in re.findall(r'led by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in people:
            results.append((p, company, "Investor"))

    for p in re.findall(r'investors include ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in people:
            results.append((p, company, "Investor"))

    # fallback (controlled)
    if not results and people:
        if any(k in text.lower() for k in KEYWORDS):
            results.append((people[0], company, "Founder"))

    return results

# =============================
# SCRAPER
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=4)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:400]
    except:
        return ""

# =============================
# FEEDS
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:150]

def fetch_all(queries, months):
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
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

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

# =============================
# RUN
# =============================

if st.button("Search"):

    queries = [
        "startup raises funding founder",
        "startup backed by investor",
        "startup founded by entrepreneur",
        "startup investors include",
        "startup funding led by",
        "startup raises seed round",
        "startup raises series A",
        "ex Google founder startup",
        "former Meta founder startup",
        "AI startup raises funding",
        "fintech startup raises funding",
        "SaaS startup raises funding"
    ]

    entries = fetch_all(queries, months)

    company_results = {}
    seen = set()

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]
        text = title + ". " + fetch_text(e.link)

        if not any(k in title.lower() for k in KEYWORDS):
            continue

        events = extract_events(text)

        for person, company, role in events:

            if person.lower() == company.lower():
                continue

            key = (company.lower(), person.lower())
            if key in seen:
                continue
            seen.add(key)

            if company not in company_results:
                company_results[company] = {
                    "people": set(),
                    "title": title,
                    "link": e.link
                }

            company_results[company]["people"].add((person, role))

    # =============================
    # OUTPUT
    # =============================

    if company_results:

        st.success(f"Found {len(company_results)} companies")

        for company, data in company_results.items():

            st.markdown(f"### 🏢 {company}")

            for person, role in data["people"]:
                st.markdown(f"👤 {person} — {role}")

            st.markdown(f"📰 {data['title']}")
            st.markdown(f"[Read Article]({data['link']})")

            st.divider()

    else:
        st.warning("No entrepreneur activity found")
