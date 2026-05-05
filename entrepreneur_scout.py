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

def extract_with_openai(text):
    try:
        prompt = f"""
Extract ONLY if a clear relationship exists.

Return:
- entrepreneur (person name)
- company (startup name)
- role (Founder, Investor, Operator)

If no clear relationship exists, return:
{{
  "entrepreneur": null,
  "company": null,
  "role": null
}}

Sentence:
{text}
"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        content = response.choices[0].message.content.strip()
        data = json.loads(content)

        return (
            data.get("entrepreneur"),
            data.get("company"),
            data.get("role")
        )

    except:
        return None, None, None

# ==================== REGEX FALLBACK ====================
def extract_companies_regex(text):
    pattern = r'([A-Z][A-Za-z0-9&\-\.\']+(?:\s+[A-Z][A-Za-z0-9&\-\.\']+){0,3})\s+(?:raises|lands|secures)'
    return re.findall(pattern, text)

def extract_people_regex(text):
    return re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

# ==================== APP CONFIG ====================
st.set_page_config(page_title="Track Record", layout="wide")
st.title("📊 Track Record")
st.markdown("**Find when successful entrepreneurs start or invest in a new company**")

# ==================== SOURCES ====================
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "Crunchbase News": "https://news.crunchbase.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "WIRED": "https://www.wired.com/feed/rss",
    "Forbes Tech": "https://www.forbes.com/technology/feed/",
    "Business Insider": "https://www.businessinsider.com/rss",
    "Tech.eu": "https://tech.eu/feed/",
    "Startup Daily": "https://www.startupdaily.net/feed/",
    "SmartCompany": "https://www.smartcompany.com.au/feed/",
    "InnovationAus": "https://www.innovationaus.com/feed/",
    "AFR": "https://www.afr.com/rss"
}

GOOGLE_SOURCE = "Google News"

# ==================== SIDEBAR ====================
st.sidebar.header("Track Record")
st.sidebar.markdown("Find when successful entrepreneurs start or invest in a new company")

months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

# 🔥 NEW: SHOW SOURCES IN SIDEBAR
st.sidebar.subheader("Sources")

use_google = st.sidebar.checkbox("Google News", value=True)

selected_sources = []
for source in RSS_FEEDS.keys():
    if st.sidebar.checkbox(source, value=True):
        selected_sources.append(source)

# ==================== SCRAPING ====================
@st.cache_data(ttl=3600)
def fetch_article_text(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:2000]
    except:
        return ""

# ==================== TEXT PROCESSING ====================
def split_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 40]

def is_relevant(text):
    return any(k in text.lower() for k in [
        "startup", "funding", "venture",
        "joins", "appointed", "ceo", "raises",
        "founded", "invested"
    ])

def is_roundup(text):
    return any(k in text.lower() for k in [
        "the week", "roundup", "top deals",
        "dozens of", "many startups", "list of"
    ])

# ==================== BACKGROUND ====================
def extract_backgrounds(text):
    patterns = [
        r'ex[- ]([A-Z][A-Za-z0-9&\-\.\']+)',
        r'former\s+([A-Z][A-Za-z0-9&\-\.\']+)',
        r'previously\s+(?:at\s+)?([A-Z][A-Za-z0-9&\-\.\']+)'
    ]
    results = set()
    for p in patterns:
        for m in re.findall(p, text):
            results.add(m.strip())
    return list(results)

# ==================== REPUTATION ====================
TOP_COMPANIES = {"Google","Meta","Stripe","OpenAI","Amazon","Apple","Microsoft","DeepMind"}

def calculate_reputation(role, backgrounds, appearances):
    score = 0

    for b in backgrounds:
        score += 5 if b in TOP_COMPANIES else 2

    score += appearances * 2

    if role == "Founder":
        score += 5
    elif role == "Investor":
        score += 3
    elif role == "Operator":
        score += 2

    return score

# ==================== FETCH ====================
def fetch_google(query, months):
    q = urllib.parse.quote_plus(query + " Australia")
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m&hl=en-AU&gl=AU&ceid=AU:en"
    return feedparser.parse(url).entries[:30]

# ==================== MAIN ====================
if st.button("🔍 Search"):

    queries = [
        "startup raises funding",
        "startup secures funding",
        "joins startup",
        "startup hires CEO",
        "ex Google joins startup",
        "founded startup",
        "invested in startup"
    ]

    results_dict = {}
    entrepreneur_counts = {}

    def process(entry, source):
        title = entry.title or ""
        clean = title.split(" - ")[0].strip()

        article = fetch_article_text(entry.link)
        full_text = clean + ". " + article

        if is_roundup(full_text):
            return

        sentences = split_sentences(full_text)

        for sentence in sentences:

            if not is_relevant(sentence):
                continue

            entrepreneur, company, role = extract_with_openai(sentence)

            # 🔥 FALLBACK
            if not entrepreneur or not company:
                companies = extract_companies_regex(sentence)
                people = extract_people_regex(sentence)

                if not companies or not people:
                    continue

                entrepreneur = people[0]
                company = companies[0]
                role = role if role else "Mentioned"

            backgrounds = extract_backgrounds(sentence)

            entrepreneur_counts[entrepreneur] = entrepreneur_counts.get(entrepreneur, 0) + 1

            key = (company, clean)

            if key not in results_dict:
                results_dict[key] = {
                    "Entrepreneur": entrepreneur,
                    "Company": company,
                    "Role": role,
                    "Score": 1,
                    "Background": backgrounds,
                    "Title": clean,
                    "Source": source,
                    "Link": entry.link
                }
            else:
                results_dict[key]["Score"] += 1
                results_dict[key]["Background"] = list(
                    set(results_dict[key]["Background"] + backgrounds)
                )

    # Google
    if use_google:
        for q in queries:
            for e in fetch_google(q, months):
                process(e, GOOGLE_SOURCE)

    # RSS
    for src, url in RSS_FEEDS.items():
        if src not in selected_sources:
            continue

        for e in feedparser.parse(url).entries[:30]:
            process(e, src)

    # ==================== APPLY REPUTATION ====================
    for data in results_dict.values():
        appearances = entrepreneur_counts.get(data["Entrepreneur"], 1)

        rep_score = calculate_reputation(
            data["Role"],
            data.get("Background", []),
            appearances
        )

        if data["Role"] != "Mentioned":
            data["Score"] += rep_score + 5
        else:
            data["Score"] += rep_score

    # ==================== OUTPUT ====================
    if results_dict:
        df = pd.DataFrame(results_dict.values())
        df = df.sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']} — {r['Role']}**")
            st.markdown(f"🔥 Score: {r['Score']}")

            if r.get("Background"):
                st.markdown(f"🏆 Background: {', '.join(r['Background'])}")

            st.markdown(f"📰 {r['Title']}")
            st.markdown(f"📡 {r['Source']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()

    else:
        st.error("No results found")
