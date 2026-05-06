import streamlit as st
import feedparser
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

MAX_ARTICLES = 200

# =============================
# FILTERS
# =============================

INVALID_ENTITIES = {
    "capital","ventures","vc","fund","investors",
    "global","management","group","holdings","equity",
    "angels","studios"
}

# NEW: blocks company-like words
COMPANY_WORDS = {
    "ai","labs","lab","systems","technologies",
    "tech","intelligence","solutions","platform",
    "robotics"
}

BAD_SUFFIXES = {
    "capital","ventures","studios","angels",
    "partners","group","fund"
}

KEYWORDS = [
    "founded","backed","raises","raised",
    "funding","launch","led"
]

# =============================
# HELPERS
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

    return True


def is_bad_entity(name):
    if any(w in name.lower() for w in INVALID_ENTITIES):
        return True
    if any(name.lower().endswith(s) for s in BAD_SUFFIXES):
        return True
    return False

# =============================
# COMPANY EXTRACTION (IMPROVED)
# =============================

def extract_company(text):

    # "Solve Intelligence raises"
    m = re.search(r'([A-Z][A-Za-z0-9&\-\s]+?)\s+(raises|raised|secures)', text)
    if m:
        return m.group(1).strip()

    # "startup X"
    m = re.search(r'startup\s+([A-Z][A-Za-z0-9&\-]+)', text)
    if m:
        return m.group(1)

    # "X, a startup"
    m = re.search(r'([A-Z][A-Za-z0-9&\-]+),?\s+(?:a|an)\s+startup', text)
    if m:
        return m.group(1)

    return None

# =============================
# PERSON EXTRACTION
# =============================

def extract_people(text):

    candidates = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

    people = []
    for c in candidates:

        if not is_valid_person(c):
            continue

        if is_bad_entity(c):
            continue

        people.append(c)

    return list(set(people))

# =============================
# CORE EXTRACTION
# =============================

def extract_events(text):

    company = extract_company(text)
    if not company:
        return []

    people = extract_people(text)
    results = []

    # founded by
    for p in re.findall(r'founded by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in people:
            results.append((p, company, "Founder"))

    # backed by
    for p in re.findall(r'backed by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in people:
            results.append((p, company, "Investor"))

    # investor fallback
    if not results:
        for p in people:
            if "backed" in text.lower() or "led" in text.lower():
                results.append((p, company, "Investor"))

    # founder fallback
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
        return " ".join(p.get_text() for p in soup.find_all("p"))[:500]
    except:
        return ""

# =============================
# FEEDS
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:80]

def fetch_all(queries, months):
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
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
        "startup founded by",
        "startup backed by",
        "startup raises funding founder",
        "startup raises funding investor",
        "startup backed by entrepreneur",
        "startup raises funding led by"
    ]

    entries = fetch_all(queries, months)

    company_results = {}

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]
        text = title + ". " + fetch_text(e.link)

        if not any(k in title.lower() for k in KEYWORDS):
            continue

        events = extract_events(text)

        for person, company, role in events:

            # 🚨 critical fix
            if person.lower() == company.lower():
                continue

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
