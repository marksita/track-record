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

STOPWORDS = {
    "week","wind","supply","legal","group","company",
    "startup","firm","business","tech","data","ai","former"
}

INVALID_ENTITIES = {
    "partners","capital","ventures","vc","fund","investors",
    "global","management","group","holdings","equity","angels","studios"
}

KNOWN_FUNDS = {
    "Tiger Global","Sequoia Capital","Andreessen Horowitz",
    "Accel","Benchmark","SoftBank","Kleiner Perkins"
}

BAD_PERSON_SUFFIXES = {
    "capital","ventures","studios","angels","partners","group","fund"
}

ELITE_KEYWORDS = [
    "ex-google","former google","google alumni",
    "ex-stripe","former stripe",
    "openai","deepmind","meta","facebook",
    "apple","amazon","microsoft"
]

# =============================
# HELPERS
# =============================

def is_valid_person(name):
    parts = name.split()
    return (
        len(parts) == 2
        and all(p[0].isupper() for p in parts)
        and all(p.isalpha() for p in parts)
    )

def is_company_like(name):
    if name in KNOWN_FUNDS:
        return True
    if any(w in name.lower() for w in INVALID_ENTITIES):
        return True
    if any(name.lower().endswith(s) for s in BAD_PERSON_SUFFIXES):
        return True
    return False

# =============================
# COMPANY EXTRACTION (FIXED)
# =============================

def extract_company(text):

    # "X raises $..."
    m = re.search(r'([A-Z][A-Za-z0-9&\-\']+)\s+(raises|raised|secures)', text)
    if m:
        return m.group(1)

    # "startup X"
    m = re.search(r'startup\s+([A-Z][A-Za-z0-9&\-\']+)', text)
    if m:
        return m.group(1)

    # "X, a startup"
    m = re.search(r'([A-Z][A-Za-z0-9&\-\']+),?\s+(?:a|an)\s+startup', text)
    if m:
        return m.group(1)

    return None

# =============================
# PERSON EXTRACTION (STRICT)
# =============================

def extract_people(text):

    candidates = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

    people = []
    for c in candidates:

        if not is_valid_person(c):
            continue

        if is_company_like(c):
            continue

        people.append(c)

    return list(set(people))

# =============================
# PATTERN EXTRACTION
# =============================

def extract_patterns(text):

    results = []
    company = extract_company(text)

    if not company:
        return results

    # founded by
    for group in re.findall(
        r'founded by ([A-Z][a-z]+ [A-Z][a-z]+(?:, [A-Z][a-z]+ [A-Z][a-z]+)*)',
        text
    ):
        for p in extract_people(group):
            results.append((p, company, "Founder"))

    # backed by
    for p in re.findall(r'backed by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in extract_people(p):
            results.append((p, company, "Investor"))

    # elite signal (SAFE)
    if any(k in text.lower() for k in ELITE_KEYWORDS):
        people = extract_people(text)
        if people:
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
        return " ".join(p.get_text() for p in soup.find_all("p"))[:600]
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
        "ex Google founder startup",
        "former Stripe founder startup",
        "OpenAI founder startup"
    ]

    entries = fetch_all(queries, months)

    company_results = {}

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]
        text = title + ". " + fetch_text(e.link)

        events = extract_patterns(text)

        if not events:
            continue

        company = extract_company(text)
        if not company:
            continue

        if company not in company_results:
            company_results[company] = {
                "people": set(),
                "title": title,
                "link": e.link
            }

        for p, _, role in events:
            company_results[company]["people"].add((p, role))

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
