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
Extract:
- entrepreneur
- company
- role (Founder, Investor, Operator or null)

Return nulls if unclear.

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

# ==================== REGEX ====================
def extract_companies_regex(text):
    return re.findall(r'([A-Z][A-Za-z0-9&\-\.\']+(?:\s+[A-Z][A-Za-z0-9&\-\.\']+){0,3})', text)

def extract_people_regex(text):
    return re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

# ==================== FILTERS ====================
def is_operator_noise(text):
    return any(k in text.lower() for k in [
        "engineer", "developer", "employee", "staff"
    ])

def is_strong_action(text):
    return any(k in text.lower() for k in [
        "founded", "co-founded", "launched",
        "raises", "raised", "funding",
        "backed", "invested", "led round"
    ])

def is_valid_signal(role, text):
    if role in ["Founder", "Investor"]:
        return True
    if is_strong_action(text):
        return True
    return False

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
        return " ".join(p.get_text() for p in soup.find_all("p"))[:1200]
    except:
        return ""

def split_sentences(text):
    return re.split(r'(?<=[.!?])\s+', text)

# ==================== GOOGLE ====================
countries = ["", "Australia", "US", "UK", "Europe"]

def fetch_google(query, months):
    all_entries = []
    for c in countries:
        q = urllib.parse.quote_plus(query + " " + c)
        url = f"https://news.google.com/rss/search?q={q}+when:{months}m&hl=en&gl=US&ceid=US:en"
        all_entries += feedparser.parse(url).entries[:20]
    return all_entries[:80]

# ==================== MAIN ====================
if st.button("🔍 Search"):

    queries = [
        "raises funding",
        "backed by",
        "founded startup",
        "co-founded",
        "launches company",
        "invested in",
        "led funding round"
    ]

    results = {}

    def process(entry, source):
        title = entry.title.split(" - ")[0]

        full_text = title + ". " + fetch_article_text(entry.link)

        sentences = split_sentences(full_text)[:10]

        for s in sentences:

            if is_operator_noise(s):
                continue

            person, company, role = extract_with_openai(s)

            # fallback
            if not company:
                comps = extract_companies_regex(s)
                if not comps:
                    continue
                company = comps[0]

            if not person:
                people = extract_people_regex(s)
                if not people:
                    continue
                person = people[0]

            if not is_valid_signal(role, s):
                continue

            key = (company, person)

            results[key] = {
                "Entrepreneur": person,
                "Company": company,
                "Role": role or "Signal",
                "Title": title,
                "Source": source,
                "Link": entry.link
            }

    # Google
    if use_google:
        for q in queries:
            for e in fetch_google(q, months):
                process(e, GOOGLE_SOURCE)

    # RSS
    for src in selected_sources:
        for e in feedparser.parse(RSS_FEEDS[src]).entries[:50]:
            process(e, src)

    # ==================== OUTPUT ====================
    if results:
        df = pd.DataFrame(results.values())

        st.success(f"✅ Found {len(df)} entrepreneur signals")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']} — {r['Role']}**")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"📡 {r['Source']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()

    else:
        st.warning("No entrepreneur activity found")
