
import streamlit as st
from ddgs import DDGS
from datetime import datetime

# --------------------------------
# PAGE SETTINGS
# --------------------------------

st.set_page_config(
    page_title="Global Masters AI",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Global Master's University Finder")
st.caption("Worldwide Master's University Search | Europe Priority")

st.write(
    "Find Master's programs around the world. "
    "Compare admission intakes, tuition fees, documents and deadlines."
)

# --------------------------------
# SEARCH PREFERENCES
# --------------------------------

st.sidebar.header("Search Preferences")

course = st.sidebar.text_input(
    "Master's Course",
    value="Mechanical Engineering"
)

country = st.sidebar.text_input(
    "Country (Leave blank for worldwide search)",
    value=""
)

year = st.sidebar.selectbox(
    "Admission Year",
    ["2027", "2028"]
)

intakes = st.sidebar.multiselect(
    "Select Admission Intake",
    ["February", "March", "April"],
    default=["February", "March", "April"]
)

st.info(
    "🌍 Search universities worldwide, with Europe as a priority. "
    "Always verify admission information using official university websites."
)

# --------------------------------
# SEARCH FUNCTION
# --------------------------------

def search_universities(query):

    with DDGS(timeout=20) as ddgs:

        results = list(
            ddgs.text(
                query,
                max_results=5,
                backend="bing,google"
            )
        )

    return results


# --------------------------------
# FIND UNIVERSITIES BUTTON
# --------------------------------

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
                f"Searching {intake} {year} admission information..."
            )

            query = (
                f"{course} Master's admission {intake} {year} "
                f"Europe universities official admission page "
                f"tuition fees application deadline required documents"
            )

            if country.strip():
                query += f" {country}"

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


# --------------------------------
# DISPLAY RESULTS
# --------------------------------

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
                "Search temporarily failed for this intake. "
                "Please try again later."
            )

            with st.expander("Technical details"):
                st.write(data["error"])

            continue

        results = data["results"]

        if not results:

            st.info("No search results found for this intake.")
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

            with st.container(border=True):

                st.subheader("🎓 " + title)

                st.write("**Course:** " + searched_course)

                st.write(
                    "**Admission Intake:** "
                    + intake + " " + searched_year
                )

                st.write("**Admission Information:**")

                st.write(
                    description
                    if description
                    else "Information not available in search result."
                )

                st.write("**Required Documents:**")
                st.write(
                    "Not confirmed. Check the official university admission page."
                )

                st.write("**Tuition Fee:**")
                st.write(
                    "Not confirmed. Check the official university fee page."
                )

                st.write("**Application Deadline:**")
                st.write(
                    "Not confirmed. Check the official university deadline."
                )

                st.warning(
                    "Search results do not confirm that this university "
                    "offers the selected intake. Verify directly with the university."
                )

                if url:
                    st.link_button(
                        "🌐 Visit Source Website",
                        url
                    )

# --------------------------------
# FOOTER
# --------------------------------

st.divider()

st.caption(
    "Global Masters AI | University Research Assistant"
)
