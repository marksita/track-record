import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor
import json

client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

MAX_ARTICLES = 40

# =============================
# PATTERN EXTRACTION (CORE)
# =============================

def extract_patterns(text):
    results = []

    patterns = [
        (r'([A-Z][a-z]+ [A-Z][a-z]+).*?(founded|co-founded|launched|started).*?([A-Z][A-Za-z0-9&\-\.\']+)', "Founder"),
        (r'([A-Z][a-z]+ [A-Z][a-z]+).*?(invested in|backed|led).*?([A-Z][A-Za-z0-9&\-\.\']+)', "Investor"),
        (r'([A-Z][A-Za-z0-9&\-\.\']+).*?(raised|funding).*?(from|led by).*?([A-Z][a-z]+ [A-Z][a-z]+)', "Investor")
    ]

    for pattern, role in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if role == "Investor" and len(m) == 4:
                company, _, _, person = m
            else:
                person, _, company = m

            results.append({
                "entrepreneur": person,
                "company": company,
                "role": role
            })

    return results

# =============================
# OPENAI (OPTIONAL ENRICH)
# =============================

@st.cache_data(ttl=86400)
def enrich_with_openai(text):
    try:
        prompt = f"""
Extract entrepreneur background (e.g. ex-Google, former Stripe).

Text:
{text}

Return JSON:
{{"background": "..."}}
"""
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0
        )
        return json.loads(r.choices[0].message.content.strip())
    except:
        return {}

# =============================
# SCRAPER
# =============================

@st.cache_data(ttl=3600)
def fetch_text(url):
    try:
        r = requests.get(url, timeout=4)
        soup = BeautifulSoup(r.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:600]
    except:
        return ""

# =============================
# GOOGLE
# =============================

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m"
    return feedparser.parse(url).entries[:25]

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
st.markdown("**Find when successful entrepreneurs start or invest in a new company**")

months = st.sidebar.slider("Lookback (months)",1,12,12)

# =============================
# RUN
# =============================

if st.button("🔍 Search"):

    queries = [
        "startup raises funding",
        "founded startup",
        "co-founded startup",
        "invested in startup",
        "backed startup",
        "led funding round"
    ]

    entries = fetch_all(queries, months)

    results = {}

    for e in entries:

        title = e.title.split(" - ")[0]
        text = title

        # scrape only strong signals
        if any(k in title.lower() for k in ["raised","founded","invested","backed"]):
            text += ". " + fetch_text(e.link)

        events = extract_patterns(text)

        for ev in events:

            person = ev["entrepreneur"]
            company = ev["company"]

            if not person or not company:
                continue

            key = (person, company)

            if key not in results:

                enrich = enrich_with_openai(text)

                results[key] = {
                    "Entrepreneur": person,
                    "Company": company,
                    "Role": ev["role"],
                    "Background": enrich.get("background",""),
                    "Title": title,
                    "Link": e.link
                }

    # =============================
    # OUTPUT
    # =============================

    if results:

        df = pd.DataFrame(results.values())

        st.success(f"✅ Found {len(df)} entrepreneur events")

        for _, r in df.iterrows():

            st.markdown(f"### 👤 {r['Entrepreneur']}")

            if r["Background"]:
                st.markdown(f"🏆 {r['Background']}")

            st.markdown(f"**{r['Role']} → 🏢 {r['Company']}**")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")

            st.divider()

    else:
        st.warning("No entrepreneur activity found")
