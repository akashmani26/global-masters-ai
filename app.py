
import streamlit as st
from ddgs import DDGS
from urllib.parse import urlparse
from datetime import datetime

st.set_page_config(
    page_title="Global Masters AI",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Global Master's University Finder")
st.caption("Worldwide Master's Search | Europe Priority")

st.write(
    "Find universities, Master's courses, admission intakes, "
    "tuition fees and application information."
)

# Search options on the MAIN SCREEN (mobile friendly)

st.subheader("🔎 Search Universities")

search_text = st.text_input(
    "Search course or university name",
    placeholder="Example: Mechanical Engineering or TU Munich"
)

col1, col2 = st.columns(2)

with col1:
    country = st.text_input(
        "Country (leave blank for worldwide)",
        placeholder="Germany, Poland, Austria..."
    )

with col2:
    year = st.selectbox(
        "Admission year",
        ["2027", "2028"]
    )

intakes = st.multiselect(
    "Select intake",
    ["February", "March", "April"],
    default=["February", "March", "April"]
)

st.caption(
    "Search is free. No API key or payment required."
)

# Known education directories, not universities
DIRECTORY_DOMAINS = [
    "mastersportal.com",
    "studyineurope.eu",
    "bachelorsportal.com",
    "educations.com",
    "findamasters.com",
    "hotcoursesabroad.com"
]

def is_directory(url):
    domain = urlparse(url).netloc.lower()
    return any(site in domain for site in DIRECTORY_DOMAINS)


def search_universities(query):
    with DDGS(timeout=25) as ddgs:
        return list(
            ddgs.text(
                query,
                max_results=12,
                backend="auto"
            ) or []
        )


# SEARCH

if st.button("🔍 Find Universities", type="primary"):

    if not search_text.strip():
        st.warning("Please enter a course or university name.")

    elif not intakes:
        st.warning("Please select at least one intake.")

    else:
        all_results = {}

        progress = st.progress(0)
        status = st.empty()

        for index, intake in enumerate(intakes):

            status.write(f"Searching {intake} {year} intake...")

            query = (
                f"{search_text} Master's university "
                f"{intake} {year} admission "
                f"official university website international students"
            )

            if country.strip():
                query += f" {country}"
            else:
                query += " Europe"

            try:
                results = search_universities(query)

                # Remove known education directory websites
                results = [
                    item for item in results
                    if not is_directory(item.get("href", ""))
                ]

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
        st.session_state["search_text"] = search_text
        st.session_state["search_year"] = year

        status.success("Search completed!")


# DISPLAY RESULTS

if "university_results" in st.session_state:

    st.divider()
    st.header("🎓 University Search Results")

    st.caption(
        "Search date: "
        + datetime.now().strftime("%d-%m-%Y %H:%M")
    )

    for intake, data in st.session_state["university_results"].items():

        st.subheader(f"📅 {intake} {st.session_state['search_year']}")

        if data["error"]:
            st.error(
                "Search failed. Please try again later."
            )
            with st.expander("Technical details"):
                st.code(data["error"])
            continue

        results = data["results"]

        if not results:
            st.info(
                "No suitable results found. Try another course, "
                "university or country."
            )
            continue

        for result in results:

            title = result.get("title", "University result")
            description = result.get("body", "")
            url = result.get("href", "")

            domain = (
                urlparse(url).netloc.replace("www.", "")
                if url else "Not available"
            )

            with st.container(border=True):

                # Search result title displayed prominently
                st.markdown("### 🎓 " + title)

                st.write("**University / Programme:**", title)

                st.write(
                    "**Course searched:**",
                    st.session_state["search_text"]
                )

                st.write(
                    "**Selected intake:**",
                    intake + " " + st.session_state["search_year"]
                )

                st.write("**Website domain:**", domain)

                st.write("**Search information:**")
                st.write(
                    description if description
                    else "No description available."
                )

                st.divider()

                st.markdown("#### 📄 Required Documents")
                st.write(
                    "Not verified. Check the university's official "
                    "admission requirements."
                )

                st.markdown("#### 💰 Tuition Fee")
                st.write(
                    "Not verified. Check the official fee schedule "
                    "for international students."
                )

                st.markdown("#### 📅 Application Deadline")
                st.write(
                    "Not verified. Check the official application "
                    "deadline for this intake."
                )

                st.warning(
                    "The search result title is not independently "
                    "verified as the university's name. Confirm the "
                    "university, course and intake on its official website."
                )

                if url:
                    st.link_button(
                        "🌐 Open Source Website",
                        url
                    )

st.divider()

st.caption(
    "Global Masters AI | University Research Assistant"
)
