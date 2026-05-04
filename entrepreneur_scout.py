import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Entrepreneur Scout", layout="wide")
st.title("🚀 Entrepreneur Scout")

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
        return " ".join(p.get_text() for p in soup.find_all("p"))[:3000]
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

# ==================== EXTRACTION ====================
BLOCK_WORDS = {
    "Startup", "Company", "Tech", "Legal",
    "Week", "Rounds", "Deals",
    "Swedish", "Australian", "American",
    "Meta", "Google", "DeepMind"
}

def is_valid_company(name):
    return name and len(name) >= 3 and name not in BLOCK_WORDS

def extract_companies(text):
    patterns = [
        r'([A-Z][A-Za-z0-9&\-\.\']+)\s+(?:raises|lands|secures)',
        r'(?:joins|joined|appointed)\s+(?:[A-Za-z]+\s+){0,3}?([A-Z][A-Za-z0-9&\-\.\']+)'
    ]

    companies = set()

    for p in patterns:
        matches = re.findall(p, text)
        for m in matches:
            name = m[0] if isinstance(m, tuple) else m
            if is_valid_company(name):
                companies.add(name)

    return list(companies)

def extract_people(text):
    people = set()

    patterns = [
        r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(joins|joined|appointed|hired)',
        r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:as|to become)\s+(CEO|CTO|founder)',
        r'([A-Z][a-z]+ [A-Z][a-z]+).*?(invested|backed|led)'
    ]

    for p in patterns:
        matches = re.findall(p, text)
        for m in matches:
            people.add(m[0])

    return list(people)

def extract_backgrounds(text):
    patterns = [
        r'ex[- ]([A-Z][A-Za-z0-9&\-\.\']+)',
        r'former\s+([A-Z][A-Za-z0-9&\-\.\']+)',
        r'previously\s+at\s+([A-Z][A-Za-z0-9&\-\.\']+)'
    ]

    backgrounds = set()

    for p in patterns:
        matches = re.findall(p, text)
        for m in matches:
            backgrounds.add(m)

    return list(backgrounds)

def detect_role(text):
    t = text.lower()
    if "join" in t or "appointed" in t:
        return "Operator"
    if "invest" in t:
        return "Investor"
    if "found" in t:
        return "Founder"
    return "Mentioned"

# ==================== FETCH ====================
def fetch_google(query, months):
    q = urllib.parse.quote_plus(query + " Australia")
    url = f"https://news.google.com/rss/search?q={q}+when:{months}m&hl=en-AU&gl=AU&ceid=AU:en"
    return feedparser.parse(url).entries[:30]

# ==================== UI ====================
months = st.sidebar.slider("Lookback (months)", 1, 12, 3)

# ==================== MAIN ====================
if st.button("🚀 Run Discovery"):

    queries = [
        "startup raises funding",
        "startup secures funding",
        "startup lands investment",
        "joins startup",
        "startup hires CEO",
        "ex Google joins startup",
        "former Stripe joins startup"
    ]

    results_dict = {}
    person_counts = {}

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

            if not strong_signal(sentence):
                continue

            companies = extract_companies(sentence)
            people = extract_people(sentence)
            backgrounds = extract_backgrounds(sentence)

            if not companies:
                continue

            # 🚨 kill spam sentences
            if len(companies) > 2:
                continue

            for company in companies:
                for person in people if people else ["Unknown"]:

                    key = (person, company)

                    if key not in results_dict:
                        results_dict[key] = {
                            "Entrepreneur": person,
                            "Company": company,
                            "Background": set(backgrounds),
                            "Role": detect_role(sentence),
                            "Score": 1,
                            "Titles": set([clean]),
                            "Sources": set([source]),
                            "Links": set([entry.link])
                        }
                    else:
                        results_dict[key]["Score"] += 1
                        results_dict[key]["Titles"].add(clean)
                        results_dict[key]["Sources"].add(source)
                        results_dict[key]["Links"].add(entry.link)
                        results_dict[key]["Background"].update(backgrounds)

    # Google
    for q in queries:
        for e in fetch_google(q, months):
            process(e, GOOGLE_SOURCE)

    # RSS
    for src, url in RSS_FEEDS.items():
        for e in feedparser.parse(url).entries[:40]:
            process(e, src)

    # ==================== SCORING ====================
    for (person, _), data in results_dict.items():
        person_counts[person] = person_counts.get(person, 0) + data["Score"]

    for data in results_dict.values():
        data["Score"] += person_counts.get(data["Entrepreneur"], 0)

        for bg in data["Background"]:
            if bg in ["Google", "OpenAI", "Stripe", "Meta"]:
                data["Score"] += 3

    # ==================== FINAL ====================
    final_results = []

    for data in results_dict.values():
        final_results.append({
            "Entrepreneur": data["Entrepreneur"],
            "Company": data["Company"],
            "Background": ", ".join(data["Background"]),
            "Role": data["Role"],
            "Score": data["Score"],
            "Titles": " | ".join(list(data["Titles"])[:3]),
            "Sources": ", ".join(data["Sources"]),
            "Link": list(data["Links"])[0]
        })

    if final_results:
        df = pd.DataFrame(final_results)
        df = df.sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} clean, deduplicated results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']}** — *{r['Role']}*")

            if r["Background"]:
                st.markdown(f"🏆 {r['Background']}")

            st.markdown(f"🔥 Score: {r['Score']}")
            st.markdown(f"📰 {r['Titles']}")
            st.markdown(f"📡 {r['Sources']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()

        st.download_button(
            "📥 Download CSV",
            df.to_csv(index=False).encode(),
            "results.csv"
        )

    else:
        st.error("No high-quality results found")
