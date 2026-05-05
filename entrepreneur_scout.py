import streamlit as st
import feedparser
import pandas as pd
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

# ==================== OPTIONAL NER ====================
USE_NER = False
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    USE_NER = True
except:
    USE_NER = False

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

# ==================== NER EXTRACTION ====================
def extract_with_ner(text):
    companies = set()
    people = set()

    if not USE_NER:
        return [], []

    doc = nlp(text)

    for ent in doc.ents:
        if ent.label_ == "ORG":
            companies.add(ent.text.strip())
        elif ent.label_ == "PERSON":
            people.add(ent.text.strip())

    return list(companies), list(people)

# ==================== REGEX FALLBACK ====================
BLOCK_WORDS = {
    "Startup", "Company", "Tech", "Legal",
    "Week", "Rounds", "Deals",
    "Swedish", "Australian", "American",
    "Meta", "Google", "DeepMind"
}

def is_valid_company(name):
    if not name or len(name) < 3:
        return False

    if len(name.split()) == 1 and name.lower() in [
        "supply", "capital", "ventures", "group"
    ]:
        return False

    return name not in BLOCK_WORDS

def extract_companies_regex(text):
    pattern = r'([A-Z][A-Za-z0-9&\-\.\']+(?:\s+[A-Z][A-Za-z0-9&\-\.\']+){0,3})\s+(?:raises|lands|secures)'
    matches = re.findall(pattern, text)
    return [m.strip() for m in matches if is_valid_company(m)]

def extract_people_regex(text):
    pattern = r'([A-Z][a-z]+ [A-Z][a-z]+)'
    return re.findall(pattern, text)

# ==================== BACKGROUNDS ====================
def extract_backgrounds(text):
    patterns = [
        r'ex[- ]([A-Z][A-Za-z0-9&\-\.\']+)',
        r'former\s+([A-Z][A-Za-z0-9&\-\.\']+)',
        r'previously\s+at\s+([A-Z][A-Za-z0-9&\-\.\']+)'
    ]
    results = set()
    for p in patterns:
        for m in re.findall(p, text):
            results.add(m)
    return list(results)

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

# ==================== MAIN ====================
if st.button("🔍 Search"):

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

            # 🔥 NER first, fallback to regex
            companies, people = extract_with_ner(sentence)

            if not companies:
                companies = extract_companies_regex(sentence)

            if not people:
                people = extract_people_regex(sentence)

            backgrounds = extract_backgrounds(sentence)

            if not companies:
                continue

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

    # ==================== OUTPUT ====================
    final_results = []
    for data in results_dict.values():
        final_results.append({
            "Entrepreneur": data["Entrepreneur"],
            "Company": data["Company"],
            "Score": data["Score"],
            "Titles": " | ".join(list(data["Titles"])[:3]),
            "Sources": ", ".join(data["Sources"]),
            "Link": list(data["Links"])[0]
        })

    if final_results:
        df = pd.DataFrame(final_results).sort_values(by="Score", ascending=False)

        st.success(f"✅ Found {len(df)} high-quality results")

        for _, r in df.iterrows():
            st.markdown(f"### 🏢 {r['Company']}")
            st.markdown(f"**👤 {r['Entrepreneur']}**")
            st.markdown(f"🔥 Score: {r['Score']}")
            st.markdown(f"📰 {r['Titles']}")
            st.markdown(f"📡 {r['Sources']}")
            st.markdown(f"[🔗 Read Article]({r['Link']})")
            st.divider()

    else:
        st.error("No high-quality results found")
