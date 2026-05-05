import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ==================== OPENAI ====================
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

def extract_with_openai(text):
    try:
        prompt = f"""
Extract the following from this sentence:

- Entrepreneur name
- Company name
- Role (Founder, Investor, Operator)

Return ONLY valid JSON like:
{{
  "entrepreneur": "...",
  "company": "...",
  "role": "..."
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

        # basic safety parse
        import json
        data = json.loads(content)

        return (
            [data.get("company")] if data.get("company") else [],
            [data.get("entrepreneur")] if data.get("entrepreneur") else [],
            data.get("role", "Mentioned")
        )

    except:
        return [], [], "Mentioned"

# ==================== APP CONFIG ====================
st.set_page_config(page_title="Track Record", layout="wide")
st.title("📊 Track Record")
st.markdown("**Find when successful entrepreneurs start or invest in a new company**")

# ==================== SIDEBAR ====================
st.sidebar.header("Track Record")
st.sidebar.markdown("Find when successful entrepreneurs start or invest in a new company")
months = st.sidebar.slider("Lookback (months)", 1, 12, 12)

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

# ==================== SCRAPING ====================
@st.cache_data(ttl=3600)
def fetch_article_text(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))[:2000]
    except:
        return ""

# ==================== SENTENCE SPLIT ====================
def split_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 40]

# ==================== FILTERS ====================
def is_relevant(text):
    return any(k in text.lower() for k in [
        "startup", "funding", "venture",
        "joins", "appointed", "ceo", "raises"
    ])

def strong_signal(text):
    return any(k in text.lower() for k in [
        "raises", "funding", "joins", "appointed", "hired"
    ])

def is_roundup(text):
    return any(k in text.lower() for k in [
        "the week", "roundup", "top deals",
        "dozens of", "many startups", "list of"
    ])

# ==================== FALLBACK REGEX ====================
def extract_companies_regex(text):
    pattern = r'([A-Z][A-Za-z0-9&\-\.\']+(?:\s+[A-Z][A-Za-z0-9&\-\.\']+){0,3})\s+(?:raises|lands|secures)'
    return re.findall(pattern, text)

def extract_people_regex(text):
    return re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)

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
    ]

    results_dict = {}

    def process(entry, source):
        title = entry.title or ""
        clean = title.split(" - ")[0].strip()

        article = fetch_article_text(entry.link)
        full_text = clean + ". " + article

        if is_roundup(full_text):
            return

        sentences = split_sentences(full_text)

        for sentence in sentences:

            if not is_relevant(sentence) or not strong_signal(sentence):
                continue

            # 🔥 PRIMARY: OpenAI extraction
            companies, people, role = extract_with_openai(sentence)

            # fallback
            if not companies:
                companies = extract_companies_regex(sentence)
            if not people:
                people = extract_people_regex(sentence)

            if not companies:
                continue

            for company in companies:
                for person in people if people else ["Unknown"]:

                    key = (person, company)

                    if key not in results_dict:
                        results_dict[key] = {
                            "Entrepreneur": person,
                            "Company": company,
                            "Role": role,
                            "Score": 1,
                            "Title": clean,
                            "Source": source,
                            "Link": entry.link
                        }
                    else:
                        results_dict[key]["Score"] += 1

    # Google
    for q in queries:
        for e in fetch_google(q, months):
            process(e, GOOGLE_SOURCE)

    # RSS
    for src, url in RSS_FEEDS.items():
        for e in feedparser.parse(url).entries[:30]:
            process(e, src)

    # ==================== OUTPUT ====================
    if results_dict:
        df = pd.DataFrame(results_dict.values())
        df = df.sort_values(by="Score", ascending=False)

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
