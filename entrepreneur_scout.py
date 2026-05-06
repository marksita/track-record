import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json

# ==================== OPENAI ====================
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

@st.cache_data(ttl=86400)
def extract_with_openai(text):
    try:
        prompt = f"""
Extract ONLY if a clear relationship exists.

Return JSON:
{{
  "entrepreneur": "...",
  "company": "...",
  "role": "Founder | Investor | Operator"
}}

If none, return nulls.
Sentence:
{text}
"""
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        data = json.loads(response.choices[0].message.content.strip())
        return data.get("entrepreneur"), data.get("company"), data.get("role")
    except:
        return None, None, None

# ==================== REGEX FALLBACK ====================
def extract_companies_regex(text):
    return re.findall(r'([A-Z][A-Za-z0-9&\-\.\']+(?:\s+[A-Z][A-Za-z0-9&\-\.\']+){0,3})\s+(?:raises|lands|secures)', text)

def extract_people_regex(text):
    return re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

# ==================== APP ====================
st.set_page_config(page_title="Track Record", layout="wide")
st.title("📊 Track Record")
st.markdown("**Find when successful entrepreneurs start or invest in a new company**")

# ==================== SOURCES ====================
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "Crunchbase News": "https://news.crunchbase.com/feed/",
    "Tech.eu": "https://tech.eu/feed/",
    "Startup Daily": "https://www.startupdaily.net/feed/",
    "SmartCompany": "https://www.smartcompany.com.au/feed/"
}

GOOGLE_SOURCE = "Google News"

# ==================== SIDEBAR ====================
st.sidebar.header("Track Record")
st.sidebar.markdown("Find when successful entrepreneurs start or invest in a new company")

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

st.sidebar.subheader("Sources")
use_google = st.sidebar.checkbox("Google News", True)

selected_sources = [
    s for s in RSS_FEEDS if st.sidebar.checkbox(s, True)
]

# ==================== HELPERS ====================
@st.cache_data(ttl=3600)
def fetch_article_text(url):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:1500]
    except:
        return ""

def split_sentences(text):
    return re.split(r'(?<=[.!?])\s+', text)

def is_relevant(text):
    return any(k in text.lower() for k in [
        "startup", "funding", "joins", "founded", "invested"
    ])

def strong_signal(text):
    return any(k in text.lower() for k in [
        "raises", "funding", "joins", "appointed",
        "founded", "invested", "backed"
    ])

def extract_backgrounds(text):
    return re.findall(r'ex[- ]([A-Z][A-Za-z0-9]+)|former\s+([A-Z][A-Za-z0-9]+)', text)

def calculate_reputation(role, backgrounds, appearances):
    score = appearances * 2
    score += len(backgrounds) * 3

    if role == "Founder": score += 5
    elif role == "Investor": score += 3
    elif role == "Operator": score += 2

    return score

def fetch_google(query, months):
    q = urllib.parse.quote_plus(query + " Australia")
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m&hl=en-AU&gl=AU&ceid=AU:en"
    return feedparser.parse(url).entries[:15]

# ==================== MAIN ====================
if st.button("🔍 Search"):

    queries = [
        "startup raises funding",
        "joins startup",
        "founded startup",
        "invested in startup"
    ]

    results = {}
    counts = {}

    def process(entry, source):
        title = entry.title.split(" - ")[0]

        full_text = title

        # 🚀 only scrape if strong
        if strong_signal(title):
            full_text += ". " + fetch_article_text(entry.link)

        sentences = split_sentences(full_text)[:5]  # ⚡ limit

        for s in sentences:
            if not is_relevant(s):
                continue

            # 🚀 OpenAI only for strong
            if strong_signal(s):
                person, company, role = extract_with_openai(s)
            else:
                person, company, role = None, None, None

            # fallback
            if not person or not company:
                people = extract_people_regex(s)
                companies = extract_companies_regex(s)

                if not people or not companies:
                    continue

                person = people[0]
                company = companies[0]
                role = role or "Mentioned"

            counts[person] = counts.get(person, 0) + 1

            key = (company, title)

            if key not in results:
                results[key] = {
                    "Entrepreneur": person,
                    "Company": company,
                    "Role": role,
                    "Score": 1,
                    "Background": [],
                    "Title": title,
                    "Source": source,
                    "Link": entry.link
                }
            else:
                results[key]["Score"] += 1

    # Google
    if use_google:
        for q in queries:
            for e in fetch_google(q, months):
                process(e, GOOGLE_SOURCE)

    # RSS
    for src in selected_sources:
        for e in feedparser.parse(RSS_FEEDS[src]).entries[:15]:
            process(e, src)

    # scoring
    for r in results.values():
        rep = calculate_reputation(
            r["Role"],
            r["Background"],
            counts.get(r["Entrepreneur"], 1)
        )
        r["Score"] += rep

    # display
    if results:
        df = pd.DataFrame(results.values()).sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']} — {r['Role']}**")
            st.markdown(f"🔥 Score: {r['Score']}")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"📡 {r['Source']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()
    else:
        st.error("No results found")
