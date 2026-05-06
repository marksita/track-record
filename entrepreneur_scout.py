import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json

client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

# ==================== SETTINGS ====================
MAX_ARTICLES = 40   # 🔥 hard cap (speed control)
MAX_SENTENCES = 5   # 🔥 per article

# ==================== FAST FILTER ====================
def is_strong_title(title):
    return any(k in title.lower() for k in [
        "raises", "funding", "backed",
        "founded", "launches", "invests",
        "joins", "ceo"
    ])

# ==================== OPENAI ====================
@st.cache_data(ttl=86400)
def extract_with_openai(text):
    try:
        prompt = f"""
Extract:
- entrepreneur
- company
- role (Founder or Investor)

Return nulls if unclear.

{text}
"""
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        data = json.loads(r.choices[0].message.content.strip())
        return data.get("entrepreneur"), data.get("company"), data.get("role")
    except:
        return None, None, None

# ==================== REGEX ====================
def extract_people(text):
    return re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

def extract_companies(text):
    return re.findall(r'([A-Z][A-Za-z0-9&\-\.\']+)', text)

# ==================== SCRAPER ====================
@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:800]
    except:
        return ""

# ==================== GOOGLE ====================
def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:30]

# ==================== APP ====================
st.set_page_config(page_title="Track Record", layout="wide")
st.title("📊 Track Record")
st.markdown("Find when successful entrepreneurs start or invest in a new company")

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

# ==================== RUN ====================
if st.button("🔍 Search"):

    queries = [
        "startup raises funding",
        "raises series A",
        "backed by investors",
        "founded startup",
        "invested in startup"
    ]

    # ==================== STAGE 1: FAST COLLECTION ====================
    candidates = []

    for q in queries:
        entries = fetch_google(q, months)

        for e in entries:
            title = e.title.split(" - ")[0]

            if is_strong_title(title):
                candidates.append({
                    "title": title,
                    "link": e.link,
                    "source": "Google"
                })

    # 🔥 limit work
    candidates = candidates[:MAX_ARTICLES]

    st.info(f"⚡ Processing {len(candidates)} high-signal articles")

    # ==================== STAGE 2: DEEP ANALYSIS ====================
    results = {}

    for c in candidates:

        text = c["title"]

        # only scrape if really strong
        if "raises" in text.lower() or "founded" in text.lower():
            text += ". " + fetch_text(c["link"])

        sentences = re.split(r'(?<=[.!?])\s+', text)[:MAX_SENTENCES]

        for s in sentences:

            person, company, role = extract_with_openai(s)

            if not company:
                comps = extract_companies(s)
                if not comps:
                    continue
                company = comps[0]

            if not person:
                people = extract_people(s)
                if not people:
                    continue
                person = people[0]

            key = (company, person)

            results[key] = {
                "Company": company,
                "Entrepreneur": person,
                "Role": role or "Signal",
                "Title": c["title"],
                "Source": c["source"],
                "Link": c["link"]
            }

    # ==================== OUTPUT ====================
    if results:
        df = pd.DataFrame(results.values())

        st.success(f"✅ Found {len(df)} results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"👤 {r['Entrepreneur']} — {r['Role']}")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()
    else:
        st.warning("No results found")
