"""Local Streamlit website for job discovery and applications."""

import os
import re
from datetime import date
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv

from data_store import load_history
from job_search import search_jobs
from profile_store import PROFILE_FIELDS, clear_profile, empty_profile, load_profile, save_profile
from resume_store import clear_resume, load_resume_info, save_resume


def saved_amount(value: str) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0

load_dotenv()
st.set_page_config(page_title="J*b Applicator", page_icon="✳️", layout="wide")
st.markdown("<style>.block-container{max-width:1100px;padding-top:2rem}h1{letter-spacing:-.04em}</style>", unsafe_allow_html=True)

if "loaded" not in st.session_state:
    profile = load_profile()
    for field in PROFILE_FIELDS:
        st.session_state[field] = profile[field]
    st.session_state.job_type = profile["job_type"] if profile["job_type"] in ("Job", "Internship") else "Job"
    st.session_state.salary_currency = profile["salary_currency"] if profile["salary_currency"] in ("INR", "USD", "EUR", "GBP") else "INR"
    st.session_state.salary_min_widget = saved_amount(profile["salary_min"])
    st.session_state.salary_max_widget = saved_amount(profile["salary_max"])
    try:
        st.session_state.start_date_widget = date.fromisoformat(profile["earliest_start"])
    except ValueError:
        st.session_state.start_date_widget = date.today()
    st.session_state.saved_profile = profile
    st.session_state.loaded = True
if st.session_state.pop("clear_profile_next", False):
    st.session_state.saved_profile = empty_profile()
    for field in PROFILE_FIELDS:
        st.session_state[field] = ""
    st.session_state.job_type = "Job"
    st.session_state.salary_currency = "INR"
    st.session_state.salary_min_widget = 0
    st.session_state.salary_max_widget = 0
    st.session_state.start_date_widget = date.today()
if "resume_next" in st.session_state:
    st.session_state.resume_text = st.session_state.pop("resume_next")

st.title("J*b Finder")
st.caption("Find jobs and open their application forms. Your saved profile stays on this computer.")
history = load_history()

profile_tab, find_tab, results_tab = st.tabs(["1 · Profile", "2 · Find jobs", "3 · Past results"])

with profile_tab:
    st.subheader("Your profile and job preferences")
    st.caption("Fields marked :red[*] are required for job search. Personal details and résumé are optional and stay on this computer. Never enter a job-site password.")
    uploaded = st.file_uploader("Résumé file (PDF or TXT)", type=["pdf", "txt"])
    if uploaded and st.button("Save résumé file and extract text"):
        try:
            save_resume(uploaded.name, uploaded.getvalue())
        except (OSError, ValueError) as exc:
            st.error(f"Could not save the résumé file: {exc}")
        else:
            st.success("The original résumé file is saved locally.")
            try:
                if uploaded.name.lower().endswith(".pdf"):
                    from pypdf import PdfReader
                    resume = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(uploaded.getvalue())).pages)
                else:
                    resume = uploaded.getvalue().decode("utf-8-sig")
                if resume.strip():
                    st.session_state.resume_next = resume[:12000]
                    st.rerun()
                else:
                    st.warning("The file is saved, but has no selectable text. Paste résumé text below for form answers.")
            except Exception as exc:
                st.warning(f"The file is saved, but text extraction failed: {exc}. Paste résumé text below.")
    resume_info = load_resume_info()
    if resume_info:
        st.caption(f"Saved locally: {resume_info['name']} ({resume_info['size']:,} bytes). Opening a job link does not upload it. Delete saved profile to remove this file.")
    else:
        st.caption("No original résumé file is saved yet. Earlier versions kept only extracted text, so upload the file again.")
    with st.form("profile"):
        a, b = st.columns(2)
        with a:
            st.text_input("First name", key="first_name")
            st.text_input("Last name", key="last_name")
            st.text_input("Email", key="email")
            st.text_input("Phone", key="phone")
            st.text_input("Address", key="address")
            st.text_input("City", key="city")
            st.text_input("State / province", key="state")
            st.text_input("ZIP / postal code", key="postal_code")
            st.text_input("Country", key="country")
            st.text_input("LinkedIn", key="linkedin")
            st.text_input("Years of experience", key="experience")
        with b:
            st.text_input("Desired role :red[*]", key="role")
            st.radio("Searching for :red[*]", ["Job", "Internship"], key="job_type", horizontal=True)
            st.selectbox("Salary currency :red[*]", ["INR", "USD", "EUR", "GBP"], key="salary_currency")
            st.number_input("Minimum annual salary :red[*]", min_value=0, step=1000, key="salary_min_widget")
            st.number_input("Maximum annual salary :red[*]", min_value=0, step=1000, key="salary_max_widget")
            st.date_input("Earliest available start date :red[*]", key="start_date_widget")
            st.selectbox("Work mode", ["", "On-site", "Hybrid", "Remote"], key="work_mode")
            st.text_input("Skills", key="skills")
            st.text_input("Branch / field of study", key="branch_of_study")
            st.text_input("Graduation year", key="graduation_year", placeholder="2027")
            st.text_input("Highest qualification", key="highest_qualification")
        st.text_area("Short bio", key="bio", height=90)
        st.text_area("Résumé text", key="resume_text", height=170, help="Saved locally for your reference. Opening a job site does not upload your résumé automatically.")
        st.text_area("Cover letter notes", key="cover_letter_notes", height=80)
        st.text_area("Official company career URLs (optional, one HTTPS URL per line)", key="company_career_urls", height=80)
        save_clicked = st.form_submit_button("Save profile", type="primary")
    if save_clicked:
        values = {field: st.session_state[field] for field in PROFILE_FIELDS}
        values["salary_min"] = str(st.session_state.salary_min_widget)
        values["salary_max"] = str(st.session_state.salary_max_widget)
        values["earliest_start"] = st.session_state.start_date_widget.isoformat()
        required = ["role"]
        missing = [field.replace("_", " ") for field in required if not values[field].strip()]
        if missing:
            st.error("Enter: " + ", ".join(missing))
        elif values["email"].strip() and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"].strip()):
            st.error("Enter a valid email address.")
        elif st.session_state.salary_min_widget <= 0 or st.session_state.salary_max_widget <= 0:
            st.error("Enter a minimum and maximum annual salary greater than zero.")
        elif st.session_state.salary_min_widget > st.session_state.salary_max_widget:
            st.error("Minimum annual salary must not exceed maximum annual salary.")
        elif values["graduation_year"] and not re.fullmatch(r"\d{4}", values["graduation_year"].strip()):
            st.error("Graduation year must be four digits.")
        else:
            try:
                from job_search import company_domains
                company_domains(values["company_career_urls"])
                st.session_state.saved_profile = save_profile(values)
                st.success("Profile saved.")
            except (OSError, ValueError) as exc:
                st.error(f"Could not save profile: {exc}")
    if st.button("Delete saved profile"):
        clear_profile()
        clear_resume()
        st.session_state.clear_profile_next = True
        st.rerun()

with find_tab:
    st.subheader("Find jobs")
    st.write("Search starts with LinkedIn jobs. It also checks only the official company career domains you added. Social media, video sites, and job aggregators are excluded.")
    st.caption("Annual salary range and earliest start are saved as your preferences. Listings without clear salary or start-date details require your review.")
    if st.button("Search job listings", type="primary"):
        st.session_state.search_results = []
        st.session_state.search_error = ""
        key = os.getenv("TINYFISH_API_KEY", "").strip()
        if not key:
            st.session_state.search_error = "Add TINYFISH_API_KEY to .env and restart."
        elif not all(st.session_state.saved_profile.get(field) for field in ("role", "job_type", "salary_min", "salary_max", "earliest_start")):
            st.session_state.search_error = "Save your role, job type, salary range, and earliest start date first."
        else:
            try:
                with st.spinner("TinyFish is searching LinkedIn and reading job listings…"):
                    st.session_state.search_results = search_jobs(st.session_state.saved_profile, key)
            except Exception as exc:
                st.session_state.search_error = f"TinyFish search failed: {exc}"
    if st.session_state.get("search_error"):
        st.error(st.session_state.search_error)
    applied_urls = {row.get("url") for row in history if row.get("outcome") == "submitted"}
    search_results = st.session_state.get("search_results", [])
    if "search_results" in st.session_state and not st.session_state.get("search_error"):
        if search_results:
            st.success(f"TinyFish Search + Fetch returned {len(search_results)} result(s).")
        else:
            st.warning("TinyFish completed the search but found no individual job links. Try a broader desired role or add an official company career URL.")
    for i, job in enumerate(search_results):
        with st.container(border=True):
            st.markdown(f"**{job['title']}**")
            st.write(job["snippet"] or "Open the listing to check details.")
            st.caption(f"{job.get('source', 'Search result')} · {job.get('salary_status', 'Salary not verified')}")
            if job["url"] in applied_urls:
                st.caption("Already recorded as submitted")
            if job.get("apply_url"):
                st.link_button("Use this site", job["apply_url"], key=f"use_{i}", type="primary")
                st.caption("Opens the direct application link in a new tab.")
            else:
                st.link_button("Open job listing", job["url"], key=f"listing_{i}")
                st.caption("A direct application form link was not found. Select Apply on the job listing.")

with results_tab:
    st.subheader("Past application results")
    st.caption("These are records from earlier app versions. Opening a job site does not record a new application.")
    for i, row in enumerate(reversed(load_history())):
        with st.container(border=True):
            st.write(f"**{row.get('title') or 'Application'}** · {row.get('outcome', 'unknown').replace('_', ' ').title()}")
            if row.get("url"):
                st.link_button("Open job site", row["url"], key=f"history_{i}")
            st.write(row.get("summary", ""))
            if row.get("confirmation"):
                st.caption("Confirmation: " + row["confirmation"])
    if not history:
        st.info("No applications recorded yet.")
