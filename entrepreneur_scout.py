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
# KNOWN ENTREPRENEURS
# =============================

DEFAULT_KNOWN = {
    "Bill Gates","Elon Musk","Sam Altman","Peter Thiel",
    "Mark Zuckerberg","Jeff Bezos","Reid Hoffman",
    "Marc Andreessen","Ben Horowitz","Naval Ravikant"
}

if "known_entrepreneurs" not in st.session_state:
    st.session_state.known_entrepreneurs = set(DEFAULT_KNOWN)

if "entrepreneur_counts" not in st.session_state:
    st.session_state.entrepreneur_counts = {}

# =============================
# PERSON FILTER
# =============================

def is_real_person(name):
    parts = name.split()
    if len(parts) != 2:
        return False

    banned = ["ventures","capital","group","labs","studio","ai","fund"]
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
        return " ".join(p.get_text() for p in soup.find_all("p"))[:1200]
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
- Only real people (first + last)
- If unsure, still include best guess
- If none found, return empty list

Text:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Extract founders and investors."},
                {"role": "user", "content": prompt}
            ]
        )

        return json.loads(response.choices[0].message.content)

    except:
        return {"company": None, "people": []}

# =============================
# FALLBACK EXTRACTION (STRONG)
# =============================

def fallback_extract(text):

    # company patterns
    company = None
    patterns = [
        r'([A-Z][A-Za-z0-9&\-]+)\s+(raises|raised|secures)',
        r'startup\s+([A-Z][A-Za-z0-9&\-]+)',
        r'([A-Z][A-Za-z0-9&\-]+)\s+announced'
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            company = m.group(1)
            break

    # people patterns
    names = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

    people = []
    for n in names[:3]:
        if is_real_person(n):
            people.append({"name": n, "role": "Founder"})

    return {"company": company, "people": people}

# =============================
# LAST RESORT (GUARANTEE OUTPUT)
# =============================

def last_resort(title):
    words = title.split()
    company = words[0] if words else "Unknown"
    return {
        "company": company,
        "people": [{"name": "Unknown Founder", "role": "Founder"}]
    }

# =============================
# SCORING
# =============================

def score_person(name, role):

    score = 0

    if name in st.session_state.known_entrepreneurs:
        score += 50

    score += st.session_state.entrepreneur_counts.get(name, 0) * 10

    if role == "Founder":
        score += 20
    elif role == "Investor":
        score += 15

    return score

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
    "startup raises funding","startup founded by","startup backed by",
    "startup funding led by","AI startup raises funding",
    "fintech startup raises funding","SaaS startup raises funding",
    "startup raises seed","startup raises series A"
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

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]
        text = title + ". " + fetch_text(e.link)

        # Tier 1
        data = extract_with_openai(text)

        company = data.get("company")
        people = data.get("people", [])

        # Tier 2
        if not company or not people:
            data = fallback_extract(text)
            company = data.get("company")
            people = data.get("people", [])

        # Tier 3 (guarantee)
        if not company:
            data = last_resort(title)
            company = data["company"]
            people = data["people"]

        for p in people:

            name = p.get("name")
            role = p.get("role")

            if name != "Unknown Founder" and not is_real_person(name):
                continue

            # learning
            st.session_state.entrepreneur_counts[name] = \
                st.session_state.entrepreneur_counts.get(name, 0) + 1

            if st.session_state.entrepreneur_counts[name] >= 3:
                st.session_state.known_entrepreneurs.add(name)

            score = score_person(name, role)

            if company not in results:
                results[company] = {
                    "people": [],
                    "title": title,
                    "link": e.link,
                    "score": 0
                }

            results[company]["people"].append((name, role, score))
            results[company]["score"] += score

    # =============================
    # OUTPUT
    # =============================

    sorted_results = sorted(results.items(), key=lambda x: x[1]["score"], reverse=True)

    st.success(f"Found {len(sorted_results)} companies")

    for company, data in sorted_results:

        st.markdown(f"### 🏢 {company}")

        for name, role, score in sorted(data["people"], key=lambda x: x[2], reverse=True):
            st.markdown(f"👤 {name} — {role} 🔥 {score}")

        st.markdown(f"📰 {data['title']}")
        st.markdown(f"[Read Article]({data['link']})")

        st.divider()
