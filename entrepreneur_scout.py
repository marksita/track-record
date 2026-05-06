import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from concurrent.futures import ThreadPoolExecutor

client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

MAX_ARTICLES = 40
MAX_SENTENCES = 5

# ==================== FAST TITLE SCORING ====================
def score_title(title):
    score = 0
    t = title.lower()

    keywords = [
        "raises", "funding", "backed", "founded",
        "launches", "invests", "led by",
        "ex-", "former", "co-founder"
    ]

    for k in keywords:
        if k in t:
            score += 2

    if "series" in t:
        score += 2

    return score

# ==================== OPENAI BATCH ====================
@st.cache_data(ttl=86400)
def extract_batch(sentences):
    try:
        prompt = f"""
Extract entrepreneur events.

Return JSON list:
[
{{"entrepreneur":"", "company":"", "role":"Founder/Investor"}}
]

Sentences:
{sentences}
"""
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return json.loads(r.choices[0].message.content.strip())
    except:
        return []

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

# ==================== PARALLEL FETCH ====================
def fetch_all(queries, months):
    results = []

    def task(q):
        return fetch_google(q, months)

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(task, q) for q in queries]
        for f in futures:
            results.extend(f.result())

    return results

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
        "invested in startup",
        "ex Google startup",
        "former Stripe startup"
    ]

    # ==================== FETCH ====================
    entries = fetch_all(queries, months)

    # ==================== SCORE & FILTER ====================
    candidates = []
    for e in entries:
        title = e.title.split(" - ")[0]
        s = score_title(title)

        if s >= 2:
            candidates.append({
                "title": title,
                "link": e.link,
                "score": s
            })

    # top articles only
    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)[:MAX_ARTICLES]

    st.info(f"⚡ Processing {len(candidates)} high-quality articles")

    # ==================== PROCESS ====================
    results = {}

    for c in candidates:

        text = c["title"]

        # scrape only top tier
        if c["score"] >= 4:
            text += ". " + fetch_text(c["link"])

        sentences = re.split(r'(?<=[.!?])\s+', text)[:MAX_SENTENCES]

        extracted = extract_batch(sentences)

        for item in extracted:
            person = item.get("entrepreneur")
            company = item.get("company")

            if not person or not company:
                continue

            key = (company, person)

            results[key] = {
                "Company": company,
                "Entrepreneur": person,
                "Role": item.get("role", "Signal"),
                "Title": c["title"],
                "Link": c["link"]
            }

    # ==================== OUTPUT ====================
    if results:
        df = pd.DataFrame(results.values())

        st.success(f"✅ Found {len(df)} high-quality results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"👤 {r['Entrepreneur']} — {r['Role']}")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()
    else:
        st.warning("No results found")
