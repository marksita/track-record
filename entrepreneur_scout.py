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
Extract ONLY if this sentence shows:
- a founder starting a company OR
- an investor backing a company

Return JSON:
{{
  "entrepreneur": "...",
  "company": "...",
  "role": "Founder | Investor"
}}

If not, return nulls.

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
TOP_COMPANIES = {"Google","Meta","Stripe","OpenAI","Amazon","Apple","Microsoft","DeepMind","Sequoia","a16z"}

def is_valid_role(role):
    return role in ["Founder", "Investor"]

def has_strong_background(text):
    return any(k in text for k in [
        "ex-", "former", "previously at"
    ])

def is_operator_noise(text):
    return any(k in text.lower() for k in [
        "engineer", "employee", "staff", "developer"
    ])

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

def strong_signal(text):
    return any(k in text.lower() for k in [
        "raises", "funding", "backed",
        "founded", "invested"
    ])

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
        "startup raises funding",
        "startup backed by",
        "founded startup",
        "invested in startup",
        "led funding round"
    ]

    results = {}
    counts = {}

    def process(entry, source):
        title = entry.title.split(" - ")[0]

        full_text = title

        if strong_signal(title):
            full_text += ". " + fetch_article_text(entry.link)

        sentences = split_sentences(full_text)[:8]

        for s in sentences:

            if is_operator_noise(s):
                continue

            person, company, role = extract_with_openai(s)

            if not person or not company or not is_valid_role(role):
                continue

            # must have strong background OR repetition
            background_flag = has_strong_background(s)
            counts[person] = counts.get(person, 0) + 1

            if not background_flag and counts[person] < 2:
                continue

            key = (company, person)

            if key not in results:
                results[key] = {
                    "Entrepreneur": person,
                    "Company": company,
                    "Role": role,
                    "Score": 1,
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
        for e in feedparser.parse(RSS_FEEDS[src]).entries[:50]:
            process(e, src)

    # ==================== OUTPUT ====================
    if results:
        df = pd.DataFrame(results.values()).sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} high-quality entrepreneur signals")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']} — {r['Role']}**")
            st.markdown(f"🔥 Score: {r['Score']}")
            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"📡 {r['Source']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()

    else:
        st.warning("No high-quality entrepreneur activity found")
