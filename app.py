
import streamlit as st
import requests
from datetime import datetime
from urllib.parse import urlparse

st.set_page_config(
    page_title="Global Masters AI",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Global Master's Research Assistant")
st.caption("Search Master's programmes worldwide using live web results.")

st.sidebar.header("Search Preferences")

country = st.sidebar.text_input(
    "Preferred country",
    placeholder="Germany, Italy, Austria..."
)

course = st.sidebar.text_input(
    "Preferred course",
    placeholder="Mechanical Design"
)

ielts = st.sidebar.text_input("IELTS score", "5.5")
budget = st.sidebar.text_input("Tuition budget (INR)", "1500000")
intake = st.sidebar.text_input("Preferred intake", "February 2027")

st.subheader("Ask your university question")

question = st.text_area(
    "Your question",
    placeholder="Find universities offering MSc Mechanical Design in February 2027 with IELTS 5.5..."
)

if st.button("🔍 Search Universities", type="primary"):

    if not question.strip():
        st.warning("Please enter your question.")
        st.stop()

    try:
        api_key = st.secrets["BRAVE_API_KEY"]
    except Exception:
        st.error("Brave API key is missing. Configure it in Streamlit Secrets.")
        st.stop()

    search_query = (
        f"{question} {course} {country} "
        f"Master's admissions {intake} "
        "university official tuition IELTS requirements"
    )

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }

    with st.spinner("Searching university information..."):

        try:
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params={
                    "q": search_query,
                    "count": 15,
                    "search_lang": "en"
                },
                timeout=30
            )

            response.raise_for_status()

            results = response.json().get(
                "web", {}
            ).get("results", [])

            st.subheader("University Search Results")

            st.write("Search time:", datetime.now().strftime(
                "%d-%m-%Y %H:%M"
            ))

            if not results:
                st.info("No results found. Try another search.")

            for result in results:

                title = result.get("title", "University result")
                description = result.get("description", "")
                url = result.get("url", "")

                domain = urlparse(url).netloc.lower()

                with st.container(border=True):

                    st.markdown(f"### {title}")

                    st.write(description)

                    st.caption("Source domain: " + domain)

                    if url:
                        st.markdown(
                            f"[Visit original source]({url})"
                        )

            st.info(
                "Important: These are live search results, "
                "not independently verified admissions decisions. "
                "Confirm all fees, deadlines, IELTS scores and "
                "intakes on the university's official website."
            )

        except requests.RequestException as error:
            st.error(f"Search error: {error}")

st.divider()

st.caption(
    "Global Masters AI | University research prototype"
)
