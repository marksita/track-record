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
# FETCH ARTICLE TEXT
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

Rules:
- Only real people (no firms, no locations)
- Include if likely founder or investor
- If none, return: {{"company": null, "people": []}}

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

        data = json.loads(response.choices[0].message.content)

        if not isinstance(data, dict):
            return {"company": None, "people": []}

        return data

    except Exception as e:
        print("OpenAI error:", e)
        return {"company": None, "people": []}

# =============================
# FALLBACK EXTRACTION
# =============================

def fallback_extract(text):
    company = None
    people = []

    m = re.search(r'([A-Z][A-Za-z0-9&\-]+)\s+(raises|raised|secures)', text)
    if m:
        company = m.group(1)

    names = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

    for n in names[:2]:
        people.append({"name": n, "role": "Founder"})

    return {"company": company, "people": people}

# =============================
# NEWS FETCHING
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
# QUERY ENGINE (EXPANDED)
# =============================

QUERIES = [

    # funding
    "startup raises funding",
    "startup raises seed",
    "startup raises series A",
    "startup raises series B",
    "startup secures funding",
    "startup closes funding round",

    # founder
    "startup founded by",
    "startup co-founded by",
    "founded by entrepreneur",
    "launched by entrepreneur",

    # investor
    "startup backed by",
    "startup backed by investor",
    "startup funding led by",
    "investors include startup",

    # elite
    "startup backed by Bill Gates",
    "startup backed by Elon Musk",
    "startup backed by Peter Thiel",
    "startup backed by Sam Altman",

    # VC
    "startup backed by Sequoia",
    "startup backed by Andreessen Horowitz",
    "startup backed by Tiger Global",
    "startup backed by SoftBank",

    # experience
    "former Google founder startup",
    "ex Meta founder startup",
    "former Amazon founder startup",

    # industries
    "AI startup raises funding",
    "fintech startup raises funding",
    "SaaS startup raises funding",
    "biotech startup raises funding",
    "climate startup raises funding",

    # global
    "European startup raises funding",
    "UK startup raises funding",
    "US startup raises funding",
    "India startup raises funding",

    # variants
    "raises $ million startup",
    "raises funding led by",
    "startup raises capital",

    # discovery
    "new startup raises funding",
    "startup secures investment",
]

# =============================
# UI
# =============================

st.set_page_config(page_title="Track Record", layout="wide")

st.title("📊 Track Record")
st.markdown("Find when successful entrepreneurs start or invest in a new company")

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

# =============================
# RUN SEARCH
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

        # fallback if OpenAI misses
        if not company:
            data = fallback_extract(text)
            company = data.get("company")
            people = data.get("people", [])

        if not company or not people:
            continue

        for p in people:

            name = p.get("name")
            role = p.get("role")

            if not name:
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

    # =============================
    # OUTPUT
    # =============================

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
