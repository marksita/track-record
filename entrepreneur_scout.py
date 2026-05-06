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

MAX_ARTICLES = 50
MAX_SENTENCES = 5

# ==================== TITLE SCORING ====================
def score_title(title):
    score = 0
    t = title.lower()

    keywords = [
        "raises", "funding", "backed", "founded",
        "launches", "invests", "co-founder",
        "ex-", "former"
    ]

    for k in keywords:
        if k in t:
            score += 1

    return score

# ==================== REGEX FALLBACK ====================
def extract_people(text):
    return re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

def extract_companies(text):
    return re.findall(r'([A-Z][A-Za-z0-9&\-\.\']+)', text)

# ==================== OPENAI ====================
@st.cache_data(ttl=86400)
def extract_batch(sentences):
    try:
        prompt = f"""
Extract entrepreneur events.

Return JSON list:
[{{"entrepreneur":"", "company":"", "role":"Founder/Investor"}}]

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
        return " ".join(p.get_text() for p in soup.find_all("p"))[:600]
    except:
        return ""

# ==================== GOOGLE ====================
def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:30]

# ==================== PARALLEL ====================
def fetch_all(queries, months):
    results = []

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_google, q, months) for q in queries]
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
        "co-founder startup"
    ]

    entries = fetch_all(queries, months)

    # ==================== FILTER ====================
    candidates = []
    for e in entries:
        title = e.title.split(" - ")[0]
        s = score_title(title)

        if s >= 1:  # 🔥 relaxed
            candidates.append({
                "title": title,
                "link": e.link,
                "score": s
            })

    candidates = candidates[:MAX_ARTICLES]

    st.info(f"⚡ Processing {len(candidates)} articles")

    # ==================== PROCESS ====================
    results = {}

    for c in candidates:

        text = c["title"]

        # scrape only higher score
        if c["score"] >= 2:
            text += ". " + fetch_text(c["link"])

        sentences = re.split(r'(?<=[.!?])\s+', text)[:MAX_SENTENCES]

        extracted = extract_batch(sentences)

        # ==================== AI RESULTS ====================
        for item in extracted:
            person = item.get("entrepreneur")
            company = item.get("company")

            if person and company:
                key = (company, person)
                results[key] = {
                    "Company": company,
                    "Entrepreneur": person,
                    "Role": item.get("role", "Signal"),
                    "Title": c["title"],
                    "Link": c["link"]
                }

        # ==================== FALLBACK ====================
        if not extracted:
            people = extract_people(text)
            companies = extract_companies(text)

            for p in people[:2]:
                for comp in companies[:2]:
                    key = (comp, p)
                    results[key] = {
                        "Company": comp,
                        "Entrepreneur": p,
                        "Role": "Fallback",
                        "Title": c["title"],
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
