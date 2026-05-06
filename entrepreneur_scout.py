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
    "partners","capital","ventures","vc","fund","investors",
    "global","management","group","holdings","equity","angels"
}

KNOWN_FUNDS = {
    "Tiger Global","Sequoia Capital","Andreessen Horowitz",
    "Accel","Benchmark","SoftBank","Kleiner Perkins"
}

BAD_PERSON_WORDS = {
    "angels","capital","ventures",
    "raises","funding","group","partners"
}

ELITE_KEYWORDS = [
    "ex-google","former google","google alumni",
    "ex-stripe","former stripe",
    "openai","deepmind","meta","facebook",
    "apple","amazon","microsoft",
    "serial entrepreneur","repeat founder"
]

# =============================
# HELPERS
# =============================

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

def is_clean_person(name):
    return not any(w in name.lower() for w in BAD_PERSON_WORDS)

def is_company_like(name):
    if name in KNOWN_FUNDS:
        return True
    return any(w in name.lower() for w in INVALID_ENTITIES)

def has_elite_signal(text):
    t = text.lower()
    return any(k in t for k in ELITE_KEYWORDS)

# =============================
# COMPANY EXTRACTION
# =============================

def extract_company(text):

    m = re.search(r'(?:startup|company)\s+([A-Z][A-Za-z0-9&\-\.\']+)', text)
    if m:
        c = clean_company(m.group(1))
        if c and not is_valid_person(c):
            return c

    m = re.search(r'([A-Z][A-Za-z0-9&\-\.\']+),?\s+(?:a|an)\s+(?:\w+\s)?startup', text)
    if m:
        c = clean_company(m.group(1))
        if c and not is_valid_person(c):
            return c

    for word in text.split():
        if word[0].isupper():
            c = clean_company(word)
            if c and not is_valid_person(c):
                return c

    return None

# =============================
# PERSON EXTRACTION
# =============================

def extract_people(text):
    candidates = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

    filtered = []
    for c in candidates:
        if not is_valid_person(c):
            continue
        if not is_clean_person(c):
            continue
        if is_company_like(c):
            continue
        filtered.append(c)

    return filtered

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

    # led by
    for p in re.findall(r'led by ([A-Z][a-z]+ [A-Z][a-z]+)', text):
        if p in extract_people(p):
            results.append((p, company, "Investor"))

    # =============================
    # ELITE SIGNAL (RELAXED + SAFE)
    # =============================

    elite_matches = re.findall(
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(ex|former).{0,40}?(google|meta|stripe|openai|deepmind)',
        text,
        re.IGNORECASE
    )

    for match in elite_matches:
        person = match[0]
        if person in extract_people(person):
            results.append((person, company, "Founder"))

    # fallback: elite signal but no match
    if not results and has_elite_signal(text):
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
        "OpenAI founder startup",
        "startup launched by founder"
    ]

    entries = fetch_all(queries, months)

    company_results = {}

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]
        text = title + ". " + fetch_text(e.link)

        events = extract_patterns(text)

        valid_people = [
            (p, r) for p, _, r in events
            if is_valid_person(p)
            and is_clean_person(p)
            and not is_company_like(p)
        ]

        if not valid_people:
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

        for p, r in valid_people:
            company_results[company]["people"].add((p, r))

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
