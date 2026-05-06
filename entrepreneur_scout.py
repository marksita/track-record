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

MAX_ARTICLES = 400
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =============================
# PERSON FILTER
# =============================

def is_real_person(name):
    parts = name.split()

    if len(parts) != 2:
        return False

    if not all(p[0].isupper() for p in parts):
        return False

    banned = [
        "ventures","capital","group","labs","studio",
        "ai","fund","partners","systems","intelligence"
    ]

    if any(b in name.lower() for b in banned):
        return False

    return True

# =============================
# FETCH TEXT
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=4)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:1000]
    except:
        return ""

# =============================
# OPENAI EXTRACTION
# =============================

@st.cache_data(ttl=3600)
def extract_with_openai(text):

    prompt = f"""
Extract startup activity.

Return JSON:

{{
  "company": "company name",
  "people": [
    {{"name": "full name", "role": "Founder or Investor"}}
  ]
}}

STRICT RULES:
- Only REAL HUMAN NAMES (first + last)
- NO companies, NO funds, NO organisations
- Reject anything like Ventures, Capital, Group, Labs, AI
- If unsure → exclude
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
                {"role": "system", "content": "Extract startup founders and investors."},
                {"role": "user", "content": prompt}
            ]
        )

        return json.loads(response.choices[0].message.content)

    except:
        return {"company": None, "people": []}

# =============================
# FALLBACK
# =============================

def fallback_extract(text):
    company = None
    people = []

    m = re.search(r'([A-Z][A-Za-z0-9&\-]+)\s+(raises|raised|secures)', text)
    if m:
        company = m.group(1)

    names = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

    for n in names[:2]:
        if is_real_person(n):
            people.append({"name": n, "role": "Founder"})

    return {"company": company, "people": people}

# =============================
# FEEDS
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:150]

def fetch_all(queries, months):
    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(fetch_google, q, months) for q in queries]
        for f in futures:
            results.extend(f.result())
    return results

# =============================
# QUERIES
# =============================

QUERIES = [
    "startup raises funding",
    "startup founded by",
    "startup backed by",
    "startup funding led by",
    "startup investors include",
    "AI startup raises funding",
    "fintech startup raises funding",
    "SaaS startup raises funding",
    "startup raises seed",
    "startup raises series A",
]

# =============================
# UI
# =============================

st.title("📊 Track Record")
st.markdown("Find when successful entrepreneurs start or invest in a new company")

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

# =============================
# RUN
# =============================

if st.button("Search"):

    entries = fetch_all(QUERIES, months)

    results = {}
    seen = set()

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]
        text = title + ". " + fetch_text(e.link)

        data = extract_with_openai(text)

        company = data.get("company")
        people = data.get("people", [])

        if not company:
            data = fallback_extract(text)
            company = data.get("company")
            people = data.get("people", [])

        if not company:
            continue

        for p in people:

            name = p.get("name")
            role = p.get("role")

            if not name or not is_real_person(name):
                continue

            key = (company.lower(), name.lower())
            if key in seen:
                continue
            seen.add(key)

            if company not in results:
                results[company] = {
                    "people": [],
                    "title": title,
                    "link": e.link
                }

            results[company]["people"].append((name, role))

    if results:

        st.success(f"Found {len(results)} companies")

        for company, data in results.items():

            st.markdown(f"### 🏢 {company}")

            for name, role in data["people"]:
                st.markdown(f"👤 {name} — {role}")

            st.markdown(f"📰 {data['title']}")
            st.markdown(f"[Read Article]({data['link']})")

            st.divider()

    else:
        st.warning("No entrepreneur activity found")
