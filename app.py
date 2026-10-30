

import streamlit as st
from ddgs import DDGS
from datetime import datetime
from urllib.parse import urlparse

# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Global Masters AI",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Global Master's University Finder")
st.caption("Worldwide University Search | Europe Priority")

st.write(
    "Find Master's programs worldwide and explore admission "
    "intakes, tuition fees, documents and application deadlines."
)

# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.header("🔎 Search Preferences")

course = st.sidebar.text_input(
    "Master's Course",
    value="Mechanical Engineering"
)

country = st.sidebar.text_input(
    "Country (Leave blank for worldwide)",
    value=""
)

year = st.sidebar.selectbox(
    "Admission Year",
    ["2027", "2028"]
)

intakes = st.sidebar.multiselect(
    "Select Intake",
    ["February", "March", "April"],
    default=["February", "March", "April"]
)

st.sidebar.caption(
    "Search is free. No API key or payment required."
)

st.info(
    "🌍 Search universities worldwide, with Europe as a priority. "
    "Always verify admission details on the university's official website."
)

# ==========================================
# SEARCH FUNCTION
# ==========================================

def search_universities(query):

    with DDGS(timeout=20) as ddgs:

        results = ddgs.text(
            query,
            max_results=6,
            backend="auto"
        )

    return list(results or [])


# ==========================================
# SEARCH BUTTON
# ==========================================

if st.button("🔍 Find Universities", type="primary"):

    if not course.strip():
        st.warning("Please enter your Master's course.")

    elif not intakes:
        st.warning("Please select at least one intake.")

    else:

        all_results = {}

        progress = st.progress(0)
        status = st.empty()

        for index, intake in enumerate(intakes):

            status.write(
                f"Searching {intake} {year} intake..."
            )

            if country.strip():

                query = (
                    f"{course} Master's {intake} {year} "
                    f"admission universities in {country} "
                    f"official university admissions tuition fees "
                    f"application deadline"
                )

            else:

                query = (
                    f"{course} Master's {intake} {year} "
                    f"admission universities Europe "
                    f"international students official admissions "
                    f"tuition fees application deadline"
                )

            try:

                results = search_universities(query)

                all_results[intake] = {
                    "results": results,
                    "error": None
                }

            except Exception as error:

                all_results[intake] = {
                    "results": [],
                    "error": str(error)
                }

            progress.progress((index + 1) / len(intakes))

        st.session_state["university_results"] = all_results
        st.session_state["search_course"] = course
        st.session_state["search_year"] = year

        status.success("Search completed!")


# ==========================================
# DISPLAY RESULTS
# ==========================================

if "university_results" in st.session_state:

    results_data = st.session_state["university_results"]

    searched_course = st.session_state["search_course"]
    searched_year = st.session_state["search_year"]

    st.divider()

    st.subheader("🎓 University Admission Results")

    st.caption(
        "Search date: "
        + datetime.now().strftime("%d-%m-%Y %H:%M")
    )

    for intake, data in results_data.items():

        st.header(f"📅 {intake} {searched_year} Intake")

        if data["error"]:

            st.warning(
                "Search could not be completed for this intake. "
                "Please try again later."
            )

            with st.expander("Technical details"):
                st.code(data["error"])

            continue

        results = data["results"]

        if not results:

            st.info("No results found for this intake.")
            continue

        seen_urls = set()

        for result in results:

            title = result.get(
                "title",
                "University admission result"
            )

            description = result.get("body", "")

            url = result.get("href", "")

            if url and url in seen_urls:
                continue

            if url:
                seen_urls.add(url)

            domain = (
                urlparse(url).netloc
                if url
                else "Not available"
            )

            with st.container(border=True):

                st.subheader("🎓 " + title)

                st.write("**Course:**", searched_course)

                st.write(
                    "**Selected Intake:**",
                    intake + " " + searched_year
                )

                st.write("**Admission Information:**")

                st.write(
                    description
                    if description
                    else "No description available."
                )

                st.write("**Source Website:**", domain)

                st.divider()

                st.write("### 📄 Required Documents")

                st.write(
                    "Not verified. Check the university's "
                    "official admission requirements."
                )

                st.write("### 💰 Tuition Fee")

                st.write(
                    "Not verified. Check the official university "
                    "fee schedule for international students."
                )

                st.write("### 📅 Application Deadline")

                st.write(
                    "Not verified. Check the official application "
                    "deadline for the selected intake."
                )

                st.warning(
                    "Important: A search result does not confirm "
                    "that the university offers this intake. "
                    "Verify the course, intake, eligibility, fees "
                    "and deadline directly with the university."
                )

                if url:

                    st.link_button(
                        "🌐 Open University / Source Website",
                        url
                    )

# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption(
    "Global Masters AI | University Research Assistant"
)
