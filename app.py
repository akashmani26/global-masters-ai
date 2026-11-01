import json
import re
import time
import threading
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from ddgs import DDGS
from urllib.parse import urlparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Global Masters AI", page_icon="🎓", layout="centered")
st.title("🎓 Masters Voice Assistant")
st.caption("Ask about universities, courses, fees, deadlines, admission and IELTS requirements.")

API_KEY = st.secrets.get("GEMINI_API_KEY", "")
MODEL = st.secrets.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
MODEL = st.secrets.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODELS = st.secrets.get(
    "GEMINI_FALLBACK_MODELS",
    "gemini-3.8-flash,gemini-3.6-flash")

if not API_KEY:
    st.error("Add GEMINI_API_KEY in Manage app → Settings → Secrets.")
    st.stop()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
DIRECTORY_DOMAINS = [
    "mastersportal.com", "studyineurope.eu", "bachelorsportal.com",
    "educations.com", "findamasters.com", "hotcoursesabroad.com",
    "studyportals.com", "shiksha.com", "collegedunia.com", "youtube.com",
    "wikipedia.org", "reddit.com", "quora.com", "facebook.com", "linkedin.com",
]
KEY_LINES = re.compile(
    r"(deadline|apply|application|tuition|fee|€|EUR|IELTS|TOEFL|language|requirement|"
    r"admission|semester|ECTS|credits|intake|duration|transcript|motivation|"
    r"recommendation|GPA|CGPA|eligib)", re.I)

SYSTEM = """You are a friendly voice assistant that helps students find Master's programmes.
Today's date is {today}.
Answer ONLY from the numbered sources provided with the question.
Your reply is spoken aloud, so: 1 to 4 short sentences, plain text, no markdown, no lists,
no URLs, no source numbers. Name the university or website when you give a figure or date.
If the sources do not contain the answer, or they conflict, say so plainly and tell the user
to check the official university page. Never guess fees, deadlines, or IELTS scores.
If the question is not about universities or studying abroad, politely steer back.
Always reply in English."""


# ---------- helpers ----------
def is_directory(url):
    d = urlparse(url).netloc.lower()
    return any(s in d for s in DIRECTORY_DOMAINS)


def ddg_text(query, n):
    last = None
    for backend in ["auto", "bing", "brave", "yahoo", "mojeek"]:
        for _ in range(2):
            try:
                with DDGS(timeout=20) as d:
                    items = list(d.text(query, max_results=n, backend=backend) or [])
                if items:
                    return items
            except Exception as e:
                last = e
                time.sleep(1)
    if last:
        raise last
    return []


def read_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            t.decompose()
        lines = []
        for raw in soup.get_text("\n").split("\n"):
            raw = re.sub(r"\s+", " ", raw).strip()
            if 20 <= len(raw) <= 400:
                lines.append(raw)
        picked, total = [], 0
        for line in lines:
            if KEY_LINES.search(line):
                picked.append(line)
                total += len(line)
                if total > 2500:
                    break
        return "\n".join(picked) if picked else "\n".join(lines[:15])[:1500]
    except Exception:
        return ""


# Remembers which models are out of quota, so we skip them and go
# straight to the next model instead of waiting.
@st.cache_resource
def cooldowns():
    return {}


def _gemini(system, messages, max_tokens=1500, tools=None, timeout=30):
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if tools:
        body["tools"] = tools

    models = []
    for m in [MODEL] + FALLBACK_MODELS.split(","):
        m = m.strip()
        if m and m not in models:
            models.append(m)

    cd = cooldowns()
    now = time.time()
    active = [m for m in models if cd.get(m, 0) < now] or models
    last_err = "unknown error"

    for model in active:
        for attempt in range(2):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": API_KEY, "content-type": "application/json"},
                    json=body,
                    timeout=timeout,
                )
            except requests.exceptions.RequestException as e:
                last_err = f"{model}: {e}"
                time.sleep(2)
                continue
            if r.status_code == 200:
                cands = r.json().get("candidates", [])
                if not cands:
                    return "", []
                cand = cands[0]
                parts = cand.get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                links = []
                for ch in cand.get("groundingMetadata", {}).get("groundingChunks", []):
                    w = ch.get("web") or {}
                    if w.get("uri"):
                        links.append({"title": w.get("title") or w["uri"], "url": w["uri"]})
                return text, links
            last_err = (last_err + " | " if last_err != "unknown error" else "") + f"{model} {r.status_code}: {r.text[:150]}"
            if r.status_code == 429:
                # daily quota: skip this model for 1 hour, per-minute quota: 70 seconds
                cd[model] = time.time() + (3600 if "PerDay" in r.text else 70)
                break  # go to the next model immediately
            if r.status_code in (500, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            cd[model] = time.time() + 600  # 400/403/404: wrong model name, skip for a while
            break
    raise Exception(last_err)


def claude(system, messages, max_tokens=1500):
    return _gemini(system, messages, max_tokens)[0]


def standalone_query(question, history):
    if not history:
        return question
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    try:
        q = claude(
            "Rewrite the user's latest message into one standalone web search query "
            "(max 15 words) using the conversation for context. Output only the query.",
            [{"role": "user", "content": f"Conversation:\n{convo}\n\nLatest message: {question}"}],
            max_tokens=300,
        )
        return q.strip().strip('"') or question
    except Exception:
        return question


def gather(query):
    hits = ddg_text(query + " Master's international students", 8)
    hits = [h for h in hits if not is_directory(h.get("href", ""))][:5]
    with ThreadPoolExecutor(max_workers=3) as ex:
        texts = list(ex.map(lambda h: read_page(h.get("href", "")), hits[:4]))
    texts += [""] * (len(hits) - len(texts))
    return [{"title": h.get("title", ""), "url": h.get("href", ""),
             "snippet": h.get("body", ""), "text": t} for h, t in zip(hits, texts)]


def build_context(sources):
    parts = []
    for i, s in enumerate(sources, 1):
        parts.append(f"[{i}] {s['title']}\nURL: {s['url']}\nSnippet: {s['snippet']}\n"
                     f"Page extracts:\n{s['text']}")
    return "\n\n".join(parts)[:14000]


def answer_question(question, history):
    query = standalone_query(question, history)
    try:
        sources = gather(query)
    except Exception:
        sources = []
    ctx = build_context(sources) if sources else "No sources could be retrieved."
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    msgs.append({"role": "user",
                 "content": f"Sources:\n{ctx}\n\nQuestion: {question}"})
    text = claude(SYSTEM.format(today=datetime.now().strftime("%d %B %Y")), msgs)
    text = re.sub(r"[*_#`]", "", text)
    return text, sources


# ---------- detailed research mode ----------
PROFILE_DEFAULT = """B.Tech Mechanical Engineering, 2026 batch, CGPA 8.28/10 (Sri Venkateswara College of Engineering, Tirupati, JNTUA, India)
Marksheet states Medium of Instruction: English
IELTS 5.5 overall
Skills: CATIA V5, SolidWorks, AutoCAD
Final year project: impact strength of Al2O3-ZrO2-TiO2 ceramic composites"""

WANTS_DEFAULT = """Programmes: Machine Design, Mechanical Design, Automation, Mechatronics or Materials related masters
Intake: February, March or April 2027 only
IELTS 5.5 must be accepted
Low tuition, and part-time work allowed for international students
Exclude Germany"""

RESEARCH_SYSTEM = """You are an admissions research assistant for an Indian student.
Today's date is {today}.
Use Google Search and read the OFFICIAL university or government study-portal pages.
Ignore agents, consultants, ranking sites and forums.
Never guess. If an item is not on an official page, write: Not found, check the official page.
Only include programmes that really fit the student's wishes (intake month, IELTS, field).
If nothing fits in the country, say so clearly and give the closest option with the reason it fails.
Write in English, markdown, no long introduction."""


def research_country(country, profile, wants):
    prompt = f"""Country: {country}

Student profile:
{profile}

What the student wants:
{wants}

Find up to 3 best matching Master's programmes in {country}. For EACH programme use exactly this format:

### University name - Programme name
- Intake and start date:
- Application deadline:
- Tuition fee per year (with currency):
- Other costs (application fee, insurance, etc.):
- IELTS requirement (is 5.5 accepted? yes or no):
- Minimum CGPA / percentage:
- Required documents (full list):
- Profile match: YES / NO / BORDERLINE, with one-line reason
- Part-time work rules for international students:
- Official link:
"""
    system = RESEARCH_SYSTEM.format(today=datetime.now().strftime("%d %B %Y"))
    msgs = [{"role": "user", "content": prompt}]
    try:
        return _gemini(system, msgs, max_tokens=6000,
                       tools=[{"google_search": {}}, {"url_context": {}}], timeout=150)
    except Exception:
        return _gemini(system, msgs, max_tokens=6000,
                       tools=[{"google_search": {}}], timeout=150)


FALLBACK_COUNTRIES = ["Poland", "Lithuania", "Latvia", "Czech Republic", "Hungary",
                      "Malaysia", "Japan", "Turkey", "Cyprus", "Taiwan", "South Korea", "Estonia"]


def discover_countries(profile, wants, n):
    system = RESEARCH_SYSTEM.format(today=datetime.now().strftime("%d %B %Y"))
    prompt = f"""Student profile:
{profile}

What the student wants:
{wants}

Using Google Search, list the {n} countries where English-taught Master's programmes in this field
most likely have an intake in the months the student wants, accept the student's IELTS score,
and have low tuition. Put the best chances first.
Output ONLY the country names separated by commas. No other text."""
    try:
        text, _ = _gemini(system, [{"role": "user", "content": prompt}], max_tokens=800,
                          tools=[{"google_search": {}}], timeout=90)
    except Exception:
        return FALLBACK_COUNTRIES[:n]
    names = []
    for part in re.split(r"[,\n;]", text):
        p = re.sub(r"^[\d\.\-\*\s]+", "", part).strip(" .*")
        if 2 < len(p) < 40 and p.lower() != "germany" and p not in names:
            names.append(p)
    return names[:n] or FALLBACK_COUNTRIES[:n]


SUMMARY_SYSTEM = """You write a clear final shortlist for an Indian student from research notes.
Use ONLY facts present in the notes. Never invent or guess. If a value is missing write: check official page.
Keep only programmes marked YES or BORDERLINE for the student's profile.
Output markdown: first a table with columns
University | Country | Programme | Intake | Deadline | Fee per year | IELTS 5.5 accepted | Match
then a short line on which 3 to 5 to apply to first and why (deadline urgency, fee, IELTS).
No long introduction."""


@st.cache_resource
def job_store():
    return {"lock": threading.Lock(), "status": "idle", "total": 0, "done": 0,
            "current": "", "countries": [], "results": {}, "summary": "", "error": ""}


def run_job(store, names, profile, wants, n):
    try:
        if not names:
            with store["lock"]:
                store["current"] = "choosing countries"
            names = discover_countries(profile, wants, n)
        with store["lock"]:
            store["countries"] = names
            store["total"] = len(names)
        quota_fails = 0
        for i, c in enumerate(names):
            with store["lock"]:
                store["current"] = c
            try:
                text, links = research_country(c, profile, wants)
                quota_fails = 0
            except Exception as e:
                text, links = f"Could not research this country: {e}", []
                if "429" in str(e):
                    quota_fails += 1
            with store["lock"]:
                store["results"][c] = (text, links)
                store["done"] = i + 1
            if quota_fails >= 2:
                                store["error"] = ("All Gemini models have hit their free quota. "
                                  "Wait for the daily reset (about 1:30 PM IST), "
                                  "scan fewer countries, or enable billing.")
                break
            time.sleep(5)
        good = {c: t for c, (t, _) in store["results"].items()
                if not t.startswith("Could not research")}
        if good:
            with store["lock"]:
                store["current"] = "writing final shortlist"
            notes = "\n\n".join(f"## {c}\n{t}" for c, t in good.items())[:60000]
            msg = (f"Student profile:\n{profile}\n\nWishes:\n{wants}\n\nResearch notes:\n{notes}")
            try:
                store["summary"] = _gemini(SUMMARY_SYSTEM, [{"role": "user", "content": msg}],
                                           max_tokens=4000, timeout=120)[0]
            except Exception as e:
                store["summary"] = f"Could not write the shortlist: {e}"
    except Exception as e:
        store["error"] = str(e)
    finally:
        store["status"] = "finished"
        store["current"] = ""


def render_results():
    store = job_store()
    if store["status"] == "running":
        total = max(store["total"], 1)
        st.progress(min(store["done"] / total, 1.0))
        st.info(f"Working in the background: {store['current'] or 'starting'} "
                f"({store['done']}/{store['total'] or '?'} countries done). "
                "You can lock the phone or leave this page and come back later.")
    if store["error"]:
        st.error(store["error"])
    if store["status"] == "finished" and store["countries"]:
        st.success("Research finished.")
    if store["summary"]:
        st.markdown("## ✅ Final shortlist")
        st.markdown(store["summary"])
    res = dict(store["results"])
    for c, (text, links) in res.items():
        with st.expander(f"🌍 {c}", expanded=False):
            st.markdown(text or "No result.")
            if links:
                st.markdown("**Sources**")
                seen = set()
                for s in links:
                    if s["url"] in seen:
                        continue
                    seen.add(s["url"])
                    st.markdown(f"- [{s['title']}]({s['url']})")
    if res:
        full = (store["summary"] + "\n\n---\n\n" if store["summary"] else "") + \
            "\n\n---\n\n".join(f"# {c}\n\n{t}" for c, (t, _) in res.items())
        st.download_button("⬇️ Download all (.md)", full, file_name="masters_research.md")
    st.caption("Always confirm deadlines, fees and documents on the official university website.")


def research_ui():
    store = job_store()
    st.subheader("🔎 Detailed research")
    st.caption("Runs in the background on the server and gives fees, deadlines and documents. "
               "After you press Start you can lock the phone and come back later.")
    profile = st.text_area("Your profile", PROFILE_DEFAULT, height=170)
    wants = st.text_area("What you want", WANTS_DEFAULT, height=170)
    n = st.slider("How many countries to scan", 3, 12, 5)
    countries = st.text_input("Specific countries (optional, leave empty to search all countries)", "")
    running = store["status"] == "running"
    if st.button("🚀 Start research", type="primary", disabled=running):
        names = [c.strip() for c in countries.split(",") if c.strip()]
        with store["lock"]:
            store.update({"status": "running", "total": len(names), "done": 0,
                          "current": "starting", "countries": [], "results": {},
                          "summary": "", "error": ""})
        threading.Thread(target=run_job, args=(store, names, profile, wants, n),
                         daemon=True).start()
        st.rerun()
    frag = render_results
    if hasattr(st, "fragment"):
        frag = st.fragment(run_every=5 if running else None)(render_results)
    frag()


# ---------- state ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.turn = 0

with st.sidebar:
    if st.button("🗑 New conversation"):
        st.session_state.messages = []
        st.session_state.turn += 1
        st.rerun()

mode = st.radio("Mode", ["💬 Quick voice answers", "🔎 Detailed research"],
                horizontal=True, label_visibility="collapsed")
if mode.startswith("🔎"):
    research_ui()
    st.stop()

voice_slot = st.empty()

# ---------- chat ----------
prompt = st.chat_input("Speak with the mic above, or type here...")
if prompt:
    history = [{"role": m["role"], "content": m["content"]}
               for m in st.session_state.messages]
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Searching university pages..."):
        try:
            reply, sources = answer_question(prompt, history)
        except Exception as e:
            reply, sources = ("Sorry, I could not get that answer right now. "
                              "Please try again."), []
            st.session_state["last_error"] = str(e)
    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "sources": sources})
    st.session_state.turn += 1
    st.session_state["speak"] = {"id": st.session_state.turn, "text": reply}

if not st.session_state.messages:
    st.info("Tap **Start conversation** and ask, for example: "
            "\"What is the IELTS requirement for Mechatronics at TU Chemnitz?\"")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])
        if m.get("sources"):
            with st.expander("Sources"):
                for s in m["sources"]:
                    st.markdown(f"- [{s['title'] or s['url']}]({s['url']})")

if st.session_state.get("last_error"):
    with st.expander("Technical details"):
        st.code(st.session_state["last_error"])

# ---------- voice widget ----------
VOICE_HTML = """
<div style="font-family:sans-serif;padding:10px;border:1px solid #444;border-radius:12px;">
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <button id="start" style="padding:12px 16px;border-radius:10px;border:0;background:#ff4b4b;color:#fff;font-size:16px;">🎤 Start conversation</button>
    <button id="end" style="padding:12px 16px;border-radius:10px;border:0;background:#555;color:#fff;font-size:16px;">⏹ End</button>
  </div>
  <div id="live" style="margin-top:10px;padding:10px;border-radius:8px;background:#262730;color:#fff;min-height:24px;">Tap Start conversation, then speak.</div>
</div>
<script>
const P = window.parent;
const SPEAK = __SPEAK__;
const SID = "__SID__";
const SR = P.SpeechRecognition || P.webkitSpeechRecognition;
const live = document.getElementById("live");

function sendToChat(text) {
  const all = P.document.querySelectorAll("textarea");
  const ta = all[all.length - 1];
  if (!ta) { live.textContent = "Chat box not found."; return; }
  const setter = Object.getOwnPropertyDescriptor(P.HTMLTextAreaElement.prototype, "value").set;
  setter.call(ta, text);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  setTimeout(() => {
    ta.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true}));
  }, 200);
  setTimeout(() => {
    let el = ta.parentElement;
    for (let i = 0; i < 5 && el; i++) {
      const b = el.querySelector("button");
      if (b) { b.click(); break; }
      el = el.parentElement;
    }
  }, 600);
}

let rec = null, active = false, speaking = false;
const store = P.sessionStorage;

function listen() {
  if (!SR) { live.textContent = "Speech recognition is not supported in this browser. Use Chrome."; return; }
  if (rec || speaking) return;
  rec = new SR();
  rec.lang = "en-IN";
  rec.interimResults = true;
  rec.continuous = false;
  rec.onresult = (e) => {
    let t = "";
    for (let i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
    live.textContent = "🎤 " + t;
    if (e.results[e.results.length - 1].isFinal && t.trim()) {
      active = true;
      store.setItem("gm_active", "1");
      sendToChat(t.trim());
    }
  };
  rec.onerror = (e) => { live.textContent = "Mic error: " + e.error; };
  rec.onend = () => {
    rec = null;
    if (active && !speaking) setTimeout(listen, 400);
  };
  try { rec.start(); live.textContent = "🎤 Listening..."; } catch (err) { rec = null; }
}

function stopAll() {
  active = false;
  store.removeItem("gm_active");
  if (rec) { try { rec.abort(); } catch (e) {} rec = null; }
  P.speechSynthesis.cancel();
  live.textContent = "Stopped. Tap Start conversation to talk again.";
}

function speak(text) {
  P.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-IN";
  speaking = true;
  live.textContent = "🔊 " + text;
  u.onend = u.onerror = () => {
    speaking = false;
    if (active) setTimeout(listen, 400);
  };
  P.speechSynthesis.speak(u);
}

document.getElementById("start").onclick = () => {
  active = true;
  store.setItem("gm_active", "1");
  listen();
};
document.getElementById("end").onclick = stopAll;

if (store.getItem("gm_active") === "1") active = true;
if (SPEAK && store.getItem("gm_last") !== SID) {
  store.setItem("gm_last", SID);
  speak(SPEAK.text);
} else if (active) {
  listen();
}
</script>
"""

# ---------- render widget ----------
speak_payload = st.session_state.pop("speak", None)
html = (VOICE_HTML
        .replace("__SPEAK__", json.dumps(speak_payload))
        .replace("__SID__", str(st.session_state.turn)))
with voice_slot:
    components.html(html, height=190)