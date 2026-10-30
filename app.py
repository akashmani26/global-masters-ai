import streamlit as st
from ddgs import DDGS
from datetime import datetime

st.set_page_config(
    page_title="Global Masters AI",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Global Master's Research Assistant")
st.caption("Search Master's programmes worldwide")

st.sidebar.header("Search Preferences")

country = st.sidebar.text_input("Preferred country", "Germany")
course = st.sidebar.text_input("Preferred course", "Mechanical Engineering")
ielts = st.sidebar.text_input("IELTS score", "5.5")
budget = st.sidebar.text_input("Tuition budget (INR)", "1500000")
intake = st.sidebar.text_input("Preferred intake", "February 2027")

question = st.text_area(
    "Your university question",
    "Find MSc Mechanical Engineering universities"
)

if st.button("🔍 Search Universities", type="primary"):

    if not question.strip():
        st.warning("Please enter your question.")

    else:
        search_query = (
            f"{question} {course} {country} "
            f"{intake} IELTS {ielts} "
            "tuition fees official university"
        )

        try:
            with st.spinner("Searching universities..."):

                results = DDGS().text(
                    search_query,
                    max_results=15
                )

                results = list(results)

            st.subheader("University Search Results")
            st.caption(
                "Search time: " +
                datetime.now().strftime("%d-%m-%Y %H:%M")
            )

            if not results:
                st.info("No results found. Try another search.")

            for result in results:
                with st.container(border=True):
                    st.subheader(result.get("title", "University"))
                    st.write(result.get("body", ""))
                    url = result.get("href", "")

                    if url:
                        st.markdown(f"[Visit Website]({url})")

        except Exception as error:
            st.error(f"Search error: {error}")

st.divider()

st.caption("Global Masters AI | University Research Prototype")
