import streamlit as st
import feedparser
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
import json
import re

# =============================
# CONFIG
# =============================

MAX_ARTICLES = 250   # ↓ reduce = faster
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

KEYWORDS = ["raises","raised","funding","backed","founded","led"]

# =============================
# PERSON FILTER (STRICT)
# =============================

def is_real_person(name):
    if not name:
        return False

    parts = name.split()
    if len(parts) != 2:
        return False

    if not all(p[0].isupper() for p in parts):
        return False

    banned = [
        "ventures","capital","group","labs","studio","ai","fund",
        "this","that","these","those","uk","us","czech"
    ]

    if any(b in name.lower() for b in banned):
        return False

    return True

# =============================
# COMPANY CLEANER
# =============================

def clean_company(name):
    if not name:
        return None

    name = name.strip(",. ")

    # remove bad short tokens
    if len(name) < 3:
        return None

    if name.lower() in ["this","in","uk’s","czech"]:
        return None

    return name

# =============================
# FETCH TEXT
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=3)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:800]
    except:
        return ""

# =============================
# OPENAI EXTRACTION (CONTROLLED)
# =============================

@st.cache_data(ttl=3600)
def extract_with_openai(text):

    prompt = f"""
Extract:

- Company name
- Real founders or investors (people only)

Return JSON:

{{
 "company": "name",
 "people": [
   {{"name": "First Last", "role": "Founder or Investor"}}
 ]
}}

Rules:
- Only real people (first + last name)
- NO companies, NO funds
- If none → return empty list

Text:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Extract startup founders."},
                {"role": "user", "content": prompt}
            ]
        )

        return json.loads(response.choices[0].message.content)

    except:
        return {"company": None, "people": []}

# =============================
# FAST FALLBACK (NO FAKE PEOPLE)
# =============================

def fallback_extract(text):

    company = None

    patterns = [
        r'([A-Z][A-Za-z0-9&\-]+)\s+(raises|raised|secures)',
        r'startup\s+([A-Z][A-Za-z0-9&\-]+)'
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            company = m.group(1)
            break

    return {"company": company, "people": []}  # 🔥 no fake founders

# =============================
# FEEDS
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:120]

def fetch_all(queries, months):
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(fetch_google, q, months) for q in queries]
        for f in futures:
            results.extend(f.result())
    return results

# =============================
# QUERIES
# =============================

QUERIES = [
    "startup raises funding",
    "startup raises seed",
    "startup raises series A",
    "startup backed by",
    "startup founded by",
    "startup funding led by",
    "AI startup raises funding",
    "fintech startup raises funding",
]

# =============================
# UI
# =============================

st.title("📊 Track Record")

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

# =============================
# RUN
# =============================

if st.button("Search"):

    entries = fetch_all(QUERIES, months)

    results = {}
    seen_companies = set()

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]

        # 🔥 SPEED FILTER (huge improvement)
        if not any(k in title.lower() for k in KEYWORDS):
            continue

        text = title + ". " + fetch_text(e.link)

        data = extract_with_openai(text)

        company = clean_company(data.get("company"))
        people = data.get("people", [])

        # fallback for company only
        if not company:
            data = fallback_extract(text)
            company = clean_company(data.get("company"))

        if not company:
            continue

        if company in seen_companies:
            continue
        seen_companies.add(company)

        valid_people = []

        for p in people:
            name = p.get("name")
            role = p.get("role")

            if is_real_person(name):
                valid_people.append((name, role))

        # limit to top 2 people max
        valid_people = valid_people[:2]

        results[company] = {
            "people": valid_people,
            "title": title,
            "link": e.link
        }

    # =============================
    # OUTPUT
    # =============================

    if results:

        st.success(f"Found {len(results)} companies")

        for company, data in results.items():

            st.markdown(f"### 🏢 {company}")

            if data["people"]:
                for name, role in data["people"]:
                    st.markdown(f"👤 {name} — {role}")
            else:
                st.markdown("_No confirmed founder/investor identified_")

            st.markdown(f"📰 {data['title']}")
            st.markdown(f"[Read Article]({data['link']})")

            st.divider()

    else:
        st.warning("No entrepreneur activity found")
