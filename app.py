import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from ddgs import DDGS
from urllib.parse import urlparse, urljoin
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Global Masters AI", page_icon="🎓", layout="wide")
st.title("🎓 Global Master's University Finder")
st.caption("Worldwide Master's Search | Europe Priority")

search_text = st.text_input(
    "Search course or university name",
    placeholder="Example: Mechanical Engineering or TU Munich",
)
col1, col2 = st.columns(2)
with col1:
    country = st.text_input("Country (blank = Europe)", placeholder="Germany, Poland...")
with col2:
    year = st.selectbox("Admission year", ["2027", "2028"])
intakes = st.multiselect(
    "Select intake", ["February", "March", "April"],
    default=["February", "March", "April"],
)
max_results = st.slider("Results per intake", 3, 10, 5)

DIRECTORY_DOMAINS = [
    "mastersportal.com", "studyineurope.eu", "bachelorsportal.com",
    "educations.com", "findamasters.com", "hotcoursesabroad.com",
    "studyportals.com", "shiksha.com", "collegedunia.com", "youtube.com",
    "wikipedia.org", "reddit.com", "quora.com", "facebook.com", "linkedin.com",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
LINK_WORDS = re.compile(r"admission|requirement|tuition|fee|deadline|apply|application|intake", re.I)
MONTHS = r"(January|February|March|April|May|June|July|August|September|October|November|December)"

PATTERNS = {
    "fee": (re.compile(r"(tuition|semester fee|fees?\b|€|EUR|euro|no tuition|free of charge)", re.I),
            re.compile(r"(\d|free of charge|no tuition)", re.I)),
    "deadline": (re.compile(r"(deadline|application period|apply by|closing date|applications? (open|close)|"
                            r"submit.*application|application.*until)", re.I),
                 re.compile(MONTHS + r"|\d{1,2}[./]\d{1,2}[./]\d{2,4}|20\d\d", re.I)),
    "documents": (re.compile(r"(transcript|passport|IELTS|TOEFL|motivation|letter of recommendation|"
                             r"curriculum vitae|\bCV\b|degree certificate|bachelor.{0,20}certificate|"
                             r"language (proof|certificate)|required documents|GRE|APS|CGPA|GPA)", re.I),
                  None),
}


def is_directory(url):
    d = urlparse(url).netloc.lower()
    return any(s in d for s in DIRECTORY_DOMAINS)


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if "text/html" not in r.headers.get("content-type", ""):
            return None
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def page_lines(soup):
    for t in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        t.decompose()
    text = soup.get_text("\n")
    lines = []
    for raw in text.split("\n"):
        raw = re.sub(r"\s+", " ", raw).strip()
        for s in re.split(r"(?<=[.!?])\s+", raw):
            if 20 <= len(s) <= 300:
                lines.append(s)
    return lines


def related_links(soup, base):
    host = urlparse(base).netloc
    found = []
    for a in soup.find_all("a", href=True):
        full = urljoin(base, a["href"]).split("#")[0]
        if urlparse(full).netloc != host or full == base or full.lower().endswith(".pdf"):
            continue
        if LINK_WORDS.search(a.get_text(" ") + " " + a["href"]) and full not in found:
            found.append(full)
    return found[:2]


def analyse(result, year, intake):
    url = result.get("href", "")
    data = {k: [] for k in PATTERNS}
    soup = fetch(url)
    if soup is None:
        return result, data, False
    pages = [(url, soup)]
    for link in related_links(BeautifulSoup(str(soup), "html.parser"), url):
        s = fetch(link)
        if s is not None:
            pages.append((link, s))
    seen = set()
    for src, s in pages:
        for line in page_lines(s):
            for key, (main, extra) in PATTERNS.items():
                if main.search(line) and (extra is None or extra.search(line)) and line not in seen:
                    seen.add(line)
                    data[key].append((line, src))
    for key in data:  # prefer lines mentioning the chosen year/intake
        data[key].sort(key=lambda x: (year not in x[0], intake.lower() not in x[0].lower()))
        data[key] = data[key][:4]
    return result, data, True


def search(query, n):
    with DDGS(timeout=25) as d:
        items = list(d.text(query, max_results=n * 3, backend="auto") or [])
    items = [i for i in items if not is_directory(i.get("href", ""))]
    return items[:n]


if st.button("🔍 Find Universities", type="primary"):
    if not search_text.strip():
        st.warning("Please enter a course or university name.")
    elif not intakes:
        st.warning("Please select at least one intake.")
    else:
        out = {}
        bar = st.progress(0)
        status = st.empty()
        for i, intake in enumerate(intakes):
            status.write(f"Reading official pages for {intake} {year}...")
            q = (f"{search_text} Master's {intake} {year} intake admission requirements "
                 f"tuition fee deadline international students "
                 f"{country.strip() or 'Europe'}")
            try:
                res = search(q, max_results)
                with ThreadPoolExecutor(max_workers=5) as ex:
                    analysed = list(ex.map(lambda r: analyse(r, year, intake), res))
                out[intake] = {"items": analysed, "error": None}
            except Exception as e:
                out[intake] = {"items": [], "error": str(e)}
            bar.progress((i + 1) / len(intakes))
        st.session_state.update(res=out, year=year, text=search_text)
        status.success("Done!")

if "res" in st.session_state:
    st.divider()
    st.header("🎓 Results")
    st.caption("Search date: " + datetime.now().strftime("%d-%m-%Y %H:%M"))
    labels = {"fee": "💰 Tuition / Fees", "deadline": "📅 Deadline",
              "documents": "📄 Required Documents"}

    for intake, block in st.session_state["res"].items():
        st.subheader(f"📅 {intake} {st.session_state['year']}")
        if block["error"]:
            st.error("Search failed. Try again later.")
            with st.expander("Technical details"):
                st.code(block["error"])
            continue
        if not block["items"]:
            st.info("No results. Try another course or country.")
            continue

        for result, data, ok in block["items"]:
            url = result.get("href", "")
            domain = urlparse(url).netloc.replace("www.", "")
            with st.container(border=True):
                st.markdown("### 🎓 " + result.get("title", "Result"))
                st.write("**Website:**", domain)
                st.write(result.get("body", ""))
                if not ok:
                    st.warning("Page could not be read automatically. Open the website.")
                else:
                    for key, label in labels.items():
                        st.markdown(f"#### {label}")
                        if data[key]:
                            for line, src in data[key]:
                                st.markdown(f"- {line}  \n  [source]({src})")
                        else:
                            st.write("Not found on the page. Check the official website.")
                if url:
                    st.link_button("🌐 Open Source Website", url)
                    
st.divider()
st.caption("Information is extracted directly from university pages. Always confirm on the official site before applying.")