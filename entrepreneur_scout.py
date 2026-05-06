import streamlit as st
import feedparser
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
import json

# =============================
# CONFIG
# =============================

MAX_ARTICLES = 200
KEYWORDS = ["founded", "backed", "raises", "funding", "led", "investors"]

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# =============================
# FETCH ARTICLE TEXT
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=4)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:800]
    except:
        return ""

# =============================
# OPENAI EXTRACTION (FIXED)
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
- Only include REAL people (not firms, not locations)
- Only include if clearly founder or investor
- If none found, return: {{"company": null, "people": []}}

Text:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You extract startup founders and investors."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # safety validation
        if not isinstance(data, dict):
            return {"company": None, "people": []}

        if "company" not in data or "people" not in data:
            return {"company": None, "people": []}

        return data

    except Exception as e:
        print("OpenAI error:", e)
        return {"company": None, "people": []}

# =============================
# NEWS FEEDS
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:100]

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
# RUN SEARCH
# =============================

if st.button("Search"):

    queries = [
        "startup raises funding",
        "startup backed by",
        "startup founded by",
        "startup funding led by",
        "startup investors include",
        "AI startup raises",
        "fintech startup raises",
        "seed funding startup",
        "series A startup"
    ]

    entries = fetch_all(queries, months)

    results = {}
    seen = set()

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]

        # quick filter before OpenAI call (performance)
        if not any(k in title.lower() for k in KEYWORDS):
            continue

        text = title + ". " + fetch_text(e.link)

        data = extract_with_openai(text)

        company = data.get("company")
        people = data.get("people", [])

        # allow company even if only 1 person later
        if not company:
            continue

        for p in people:
            name = p.get("name")
            role = p.get("role")

            if not name or not role:
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
