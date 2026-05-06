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

st.set_page_config(page_title="Founder Signal", layout="wide")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

MAX_ARTICLES = 200
KEYWORDS = ["raises","raised","funding","backed","founded","led"]

# =============================
# STRICT VALIDATION
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
        "this","that","uk","us","czech"
    ]

    return not any(b in name.lower() for b in banned)


def clean_company(name):
    if not name:
        return None

    name = name.strip(",. ")

    if len(name) < 3:
        return None

    bad = ["this","in","uk’s","czech","the"]

    if name.lower() in bad:
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
# OPENAI EXTRACTION
# =============================

@st.cache_data(ttl=3600)
def extract(text):

    prompt = f"""
Extract:
- Company
- Founders or investors (real people only)

Return JSON:

{{
 "company": "name",
 "people": [
   {{"name": "First Last", "role": "Founder or Investor"}}
 ]
}}

Rules:
- ONLY real people
- NO companies/funds
- If none → empty list

Text:
{text}
"""

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Extract startup founders."},
                {"role": "user", "content": prompt}
            ]
        )

        return json.loads(res.choices[0].message.content)

    except:
        return {"company": None, "people": []}

# =============================
# FALLBACK (company only)
# =============================

def fallback_company(text):

    patterns = [
        r'([A-Z][A-Za-z0-9&\-]+)\s+(raises|raised|secures)',
        r'startup\s+([A-Z][A-Za-z0-9&\-]+)'
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)

    return None

# =============================
# FETCH NEWS
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

def fetch_google(q, months):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(q)}+when:{months}m"
    return feedparser.parse(url).entries[:100]


def fetch_all(months):
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(fetch_google, q, months) for q in QUERIES]
        for f in futures:
            results.extend(f.result())
    return results

# =============================
# UI
# =============================

st.title("📊 Founder Signal")
st.markdown("Find when successful entrepreneurs start or invest in new companies")

months = st.sidebar.slider("Lookback (months)", 1, 12, 6)

# =============================
# RUN
# =============================

if st.button("Search"):

    entries = fetch_all(months)

    results = {}
    seen = set()

    for e in entries[:MAX_ARTICLES]:

        title = e.title.split(" - ")[0]

        # fast filter
        if not any(k in title.lower() for k in KEYWORDS):
            continue

        text = title + ". " + fetch_text(e.link)

        data = extract(text)

        company = clean_company(data.get("company"))
        people = data.get("people", [])

        if not company:
            company = clean_company(fallback_company(text))

        if not company or company in seen:
            continue

        seen.add(company)

        valid_people = []

        for p in people:
            name = p.get("name")
            role = p.get("role")

            if is_real_person(name):
                valid_people.append((name, role))

        results[company] = {
            "people": valid_people[:2],
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
        st.warning("No high-quality entrepreneur activity found")
