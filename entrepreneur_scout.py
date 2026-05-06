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
    return name.strip()

def is_valid_person(name):
    parts = name.split()
    return (
        len(parts) == 2
        and all(p[0].isupper() for p in parts)
        and all(p.isalpha() for p in parts)
        and not any(p.lower() in STOPWORDS for p in parts)
    )

def is_company_like(name):
    return any(w in name.lower() for w in INVALID_ENTITIES)

# =============================
# COMPANY EXTRACTION
# =============================

def extract_company(text):

    # startup Lifeforce
    m = re.search(r'(?:startup|company)\s+([A-Z][A-Za-z0-9&\-\.\']+)', text)
    if m:
        c = clean_company(m.group(1))
        if c and not is_valid_person(c):
            return c

    # Lifeforce, a startup
    m = re.search(r'([A-Z][A-Za-z0-9&\-\.\']+),?\s+(?:a|an)\s+(?:\w+\s)?startup', text)
    if m:
        c = clean_company(m.group(1))
        if c and not is_valid_person(c):
            return c

    # fallback: first valid capitalized word
    for word in text.split():
        if word[0].isupper() and not is_valid_person(word):
            c = clean_company(word)
            if c:
                return c

    return None

# =============================
# PERSON DISCOVERY
# =============================

def extract_people(text):
    return re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

def score_person(text, person):
    score = 0
    t = text.lower()

    if person.lower() in t:
        score += 1
    if "founded" in t:
        score += 3
    if "backed" in t or "invested" in t:
        score += 2
    if any(x in t for x in ["ex-google", "former google", "ex-stripe", "openai"]):
        score += 5

    return score

# =============================
# PATTERN EXTRACTION
# =============================

def extract_patterns(text):

    results = []
    company = extract_company(text)

    if not company:
        return results

    # founders
    for group in re.findall(
        r'founded by ([A-Z][a-z]+ [A-Z][a-z]+(?:, [A-Z][a-z]+ [A-Z][a-z]+)*)',
        text
    ):
        for p in re.findall(r'[A-Z][a-z]+ [A-Z][a-z]+', group):
            if is_valid_person(p):
                results.append((p, company, "Founder"))

    # backed by
    for p in re.findall(r'backed by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if is_valid_person(p) and not is_company_like(p):
            results.append((p, company, "Investor"))

    # led by
    for p in re.findall(r'led by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if is_valid_person(p) and not is_company_like(p):
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

    # HIGH-SIGNAL QUERIES
    base_queries = [
        "startup founded by entrepreneur",
        "startup backed by celebrity",
        "celebrity startup investment",
        "founder launches startup",
        "startup backed by founder",
        "startup raises funding led by founder",
        "co-founded startup",
        "startup launched by entrepreneur",
    ]

    # SEED ENTREPRENEURS
    SEED_PEOPLE = [
        "Bill Gates","Elon Musk","Sam Altman","Reid Hoffman",
        "Peter Thiel","Marc Andreessen","Naval Ravikant",
        "Serena Williams","Tony Robbins","Mark Cuban",
        "Ashton Kutcher","Richard Branson"
    ]

    seed_queries = []
    for p in SEED_PEOPLE:
        seed_queries.append(f"{p} startup")
        seed_queries.append(f"{p} backed startup")
        seed_queries.append(f"{p} founded startup")

    # INITIAL FETCH
    entries = fetch_all(base_queries + seed_queries, months)

    # =============================
    # AUTO DISCOVERY
    # =============================

    person_scores = {}

    for e in entries:
        title = e.title.split(" - ")[0]
        text = title + ". " + fetch_text(e.link)

        for p in extract_people(text):
            if not is_valid_person(p):
                continue

            s = score_person(text, p)
            person_scores[p] = person_scores.get(p, 0) + s

    top_people = [p for p, s in person_scores.items() if s >= 5][:20]

    # SECOND PASS
    extra_queries = []
    for p in top_people:
        extra_queries.append(f"{p} startup")
        extra_queries.append(f"{p} founded startup")
        extra_queries.append(f"{p} backed startup")

    entries.extend(fetch_all(extra_queries, months))

    # =============================
    # FINAL EXTRACTION
    # =============================

    company_results = {}

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]
        text = title

        if any(k in title.lower() for k in ["raised","founded","backed","funding","led","launched"]):
            text += ". " + fetch_text(e.link)

        events = extract_patterns(text)

        for person, company, role in events:

            if not is_valid_person(person):
                continue

            if is_company_like(person):
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
