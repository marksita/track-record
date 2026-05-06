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

# =============================
# SUCCESS SIGNALS
# =============================

SUCCESS_COMPANIES = {
    "Google","Meta","OpenAI","Stripe","Amazon",
    "Microsoft","Apple","DeepMind","Uber",
    "Airbnb","Sequoia","a16z","Tesla"
}

ACTION_KEYWORDS = [
    "founded",
    "co-founded",
    "launched",
    "started",
    "raised",
    "backed",
    "invested",
    "led round"
]

# =============================
# TITLE FILTER
# =============================

def title_score(title):
    t = title.lower()
    score = 0

    for k in ACTION_KEYWORDS:
        if k in t:
            score += 2

    if "ex-" in t or "former" in t:
        score += 3

    return score

# =============================
# OPENAI EXTRACTION
# =============================

@st.cache_data(ttl=86400)
def extract_event(text):
    try:
        prompt = f"""
Extract ONLY if this is about a successful entrepreneur
starting or investing in a company.

Return JSON:

{{
 "entrepreneur": "...",
 "background": "...",
 "company": "...",
 "action": "Founder or Investor"
}}

Return nulls if not relevant.

Text:
{text}
"""

        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0
        )

        return json.loads(r.choices[0].message.content.strip())

    except:
        return None

# =============================
# SCRAPER
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=4)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:500]
    except:
        return ""

# =============================
# GOOGLE
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:25]

# =============================
# PARALLEL
# =============================

def fetch_all(queries, months):
    results = []

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_google, q, months) for q in queries]
        for f in futures:
            results.extend(f.result())

    return results

# =============================
# UI
# =============================

st.set_page_config(page_title="Track Record", layout="wide")

st.title("📊 Track Record")
st.markdown(
    "**Find when successful entrepreneurs start or invest in a new company**"
)

months = st.sidebar.slider("Lookback (months)",1,12,12)

# =============================
# RUN
# =============================

if st.button("🔍 Search"):

    queries = [
        "ex Google founder raises funding",
        "former Stripe founder startup",
        "successful entrepreneur invests in startup",
        "serial founder launches company",
        "startup backed by founder",
        "co-founder launches startup"
    ]

    entries = fetch_all(queries, months)

    candidates = []

    for e in entries:
        title = e.title.split(" - ")[0]
        score = title_score(title)

        if score >= 2:
            candidates.append({
                "title": title,
                "link": e.link,
                "score": score
            })

    candidates = sorted(
        candidates,
        key=lambda x: x["score"],
        reverse=True
    )[:MAX_ARTICLES]

    results = {}

    for c in candidates:

        text = c["title"]

        if c["score"] >= 4:
            text += ". " + fetch_text(c["link"])

        event = extract_event(text)

        if not event:
            continue

        entrepreneur = event.get("entrepreneur")
        company = event.get("company")
        action = event.get("action")

        if not entrepreneur or not company:
            continue

        if action not in ["Founder","Investor"]:
            continue

        key = (entrepreneur, company)

        results[key] = {
            "Entrepreneur": entrepreneur,
            "Background": event.get("background",""),
            "Company": company,
            "Action": action,
            "Title": c["title"],
            "Link": c["link"]
        }

    # =============================
    # OUTPUT
    # =============================

    if results:

        df = pd.DataFrame(results.values())

        st.success(f"✅ Found {len(df)} entrepreneur moves")

        for _, r in df.iterrows():

            st.markdown(f"### 👤 {r['Entrepreneur']}")

            if r["Background"]:
                st.markdown(f"**Background:** {r['Background']}")

            st.markdown(f"**{r['Action']} → 🏢 {r['Company']}**")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")

            st.divider()

    else:
        st.warning("No entrepreneur activity found")
