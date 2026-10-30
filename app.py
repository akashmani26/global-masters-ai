
import streamlit as st
from ddgs import DDGS
from datetime import datetime

st.set_page_config(
    page_title="Global Masters AI",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Global Master's University Finder")
st.caption("Worldwide university search | Europe priority")

st.sidebar.header("Search Preferences")

course = st.sidebar.text_input(
    "Master's course",
    "Mechanical Engineering"
)

country = st.sidebar.text_input(
    "Country (or leave blank for worldwide)",
    ""
)

year = st.sidebar.selectbox(
    "Admission year",
    ["2027", "2028"]
)

intakes = st.multiselect(
    "Select intake",
    ["February", "March", "April"],
    default=["February", "March", "April"]
)

st.info(
    "Search worldwide universities, with Europe as a priority. "
    "Always confirm admission details from official university sources."
)

if st.button("🔍 Find Universities", type="primary"):

    if not course.strip() or not intakes:
        st.warning("Enter a course and select at least one intake.")

    else:
        all_results = {}

        with st.spinner("Searching university admission information..."):

            try:
                with DDGS() as ddgs:

                    for intake in intakes:

                        query = (
                            f"{course} Master's {intake} {year} intake "
                            f"university Europe worldwide "
                            f"tuition fees required documents "
                            f"application deadline official admissions"
                        )

                        if country.strip():
                            query += f" {country}"

                        results = list(
                            ddgs.text(query, max_results=10)
                        )

                        all_results[intake] = results

                st.session_state["university_results"] = all_results

            except Exception as error:
                st.error(f"Search error: {error}")

if "university_results" in st.session_state:

    results_data = st.session_state["university_results"]

    st.subheader("University Admission Results")

    st.caption(
        "Search date: " +
        datetime.now().strftime("%d-%m-%Y %H:%M")
    )

    for intake, results in results_data.items():

        st.header(f"📅 {intake} {year} Intake")

        if not results:
            st.info("No results found for this intake.")
            continue

        for result in results:

            title = result.get("title", "University admission result")
            description = result.get("body", "")
            url = result.get("href", "")

            with st.container(border=True):

                st.subheader("🎓 " + title)

                st.write("**Course:** " + course)

                st.write("**Intake:** " + intake + " " + year)

                st.write("**Admission information:**")
                st.write(description or "Not published in search snippet.")

                st.write("**Required documents:**")
                st.write("Check the official admission page.")

                st.write("**Tuition fee:**")
                st.write("Not confirmed — check the official fee page.")

                st.write("**Application deadline:**")
                st.write("Not confirmed — check the official deadline.")

                st.warning(
                    "Intake availability and admission eligibility "
                    "must be confirmed on the university's official website."
                )

                if url:
                    st.link_button(
                        "Visit Source Website",
                        url
                    )

st.divider()

st.caption(
    "Global Masters AI | University Research Assistant"
)
