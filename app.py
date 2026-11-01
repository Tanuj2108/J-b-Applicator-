"""Local Streamlit website for job discovery and applications."""

import os
import re
from datetime import date
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv

from agent import run_application, validate_url
from browser_apply import close_remote_session, launch_remote_browser, read_status, write_status
from data_store import delete_answer, load_answers, load_history, save_answer, save_result
from job_search import allowed_application_url, search_jobs
from profile_store import PROFILE_FIELDS, clear_profile, empty_profile, load_profile, save_profile
from question_types import split_missing_fields
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
    st.session_state.application_url = ""
    st.session_state.job_title = ""
    st.session_state.cover_letter = ""
    st.session_state.job_queue = []
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
if st.session_state.pop("clear_application_next", False):
    st.session_state.application_url = ""
    st.session_state.job_title = ""
    st.session_state.cover_letter = ""
    st.session_state.pop("last_result", None)
if "resume_next" in st.session_state:
    st.session_state.resume_text = st.session_state.pop("resume_next")
if "selected_job_next" in st.session_state:
    job = st.session_state.pop("selected_job_next")
    st.session_state.application_url = job["url"]
    st.session_state.job_title = job["title"]
    st.session_state.cover_letter = ""
    st.session_state.pop("last_result", None)

st.title("J*b Applicator")
st.caption("Find jobs, reuse approved answers, and apply with TinyFish. Your data and results stay in local JSON files.")
history = load_history()
c1, c2, c3 = st.columns(3)
c1.metric("Confirmed applications", sum(row.get("outcome") == "submitted" and bool(row.get("confirmation")) for row in history))
c2.metric("Attempts recorded", len(history))
c3.metric("Answers remembered", len(load_answers()))

profile_tab, find_tab, apply_tab, results_tab = st.tabs(["1 · Profile", "2 · Find jobs", "3 · Apply", "4 · Results"])

with profile_tab:
    st.subheader("Your profile and job preferences")
    st.caption("Fields marked :red[*] are required. Save personal details here; never enter a job-site password.")
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
        st.caption(f"Saved locally: {resume_info['name']} ({resume_info['size']:,} bytes). Delete saved profile to remove this file.")
    else:
        st.caption("No original résumé file is saved yet. Earlier versions kept only extracted text, so upload the file again.")
    with st.form("profile"):
        a, b = st.columns(2)
        with a:
            st.text_input("First name :red[*]", key="first_name")
            st.text_input("Last name :red[*]", key="last_name")
            st.text_input("Email :red[*]", key="email")
            st.text_input("Phone :red[*]", key="phone")
            st.text_input("Address :red[*]", key="address")
            st.text_input("City :red[*]", key="city")
            st.text_input("State / province :red[*]", key="state")
            st.text_input("ZIP / postal code :red[*]", key="postal_code")
            st.text_input("Country :red[*]", key="country")
            st.text_input("LinkedIn", key="linkedin")
            st.text_input("Years of experience", key="experience")
        with b:
            st.text_input("Desired role :red[*]", key="role")
            selected_kind = st.radio("Applying for :red[*]", ["Job", "Internship"], key="job_type", horizontal=True)
            st.selectbox("Salary currency :red[*]", ["INR", "USD", "EUR", "GBP"], key="salary_currency")
            st.number_input("Minimum annual salary :red[*]", min_value=0, step=1000, key="salary_min_widget")
            st.number_input("Maximum annual salary :red[*]", min_value=0, step=1000, key="salary_max_widget")
            st.date_input("Earliest available start date :red[*]", key="start_date_widget")
            st.selectbox("Work mode", ["", "On-site", "Hybrid", "Remote"], key="work_mode")
            st.text_input("Skills", key="skills")
            st.text_input("Branch / field of study" + (" :red[*]" if selected_kind == "Internship" else ""), key="branch_of_study")
            st.text_input("Graduation year" + (" :red[*]" if selected_kind == "Internship" else ""), key="graduation_year", placeholder="2027")
            st.text_input("Highest qualification" + (" :red[*]" if selected_kind == "Internship" else ""), key="highest_qualification")
        st.text_area("Short bio", key="bio", height=90)
        st.text_area("Résumé text :red[*]", key="resume_text", height=170, help="Used to answer form fields. The original file is stored separately; TinyFish Agent cannot attach it to a job site.")
        st.text_area("Cover letter notes", key="cover_letter_notes", height=80)
        st.text_area("Official company career URLs (optional, one HTTPS URL per line)", key="company_career_urls", height=80)
        save_clicked = st.form_submit_button("Save profile", type="primary")
    if save_clicked:
        values = {field: st.session_state[field] for field in PROFILE_FIELDS}
        values["salary_min"] = str(st.session_state.salary_min_widget)
        values["salary_max"] = str(st.session_state.salary_max_widget)
        values["earliest_start"] = st.session_state.start_date_widget.isoformat()
        required = ["first_name", "last_name", "email", "phone", "address", "city", "state", "postal_code", "country", "role", "resume_text"]
        if values["job_type"] == "Internship":
            required.extend(("branch_of_study", "graduation_year", "highest_qualification"))
        missing = [field.replace("_", " ") for field in required if not values[field].strip()]
        if missing:
            st.error("Enter: " + ", ".join(missing))
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"].strip()):
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
    if search_results:
        selected_indices = st.multiselect(
            "Select jobs to review one by one",
            options=[i for i, job in enumerate(search_results) if job.get("applyable", True)],
            format_func=lambda i: search_results[i]["title"],
        )
        if st.button("Add selected jobs to queue"):
            existing = {item["url"] for item in st.session_state.job_queue}
            for i in selected_indices:
                if search_results[i]["url"] not in existing:
                    st.session_state.job_queue.append(search_results[i])
                    existing.add(search_results[i]["url"])
            st.success(f"{len(st.session_state.job_queue)} job(s) waiting for review.")
    for i, job in enumerate(search_results):
        with st.container(border=True):
            st.markdown(f"**{job['title']}**")
            st.write(job["snippet"] or "Open the listing to check details.")
            st.caption(f"{job.get('source', 'Search result')} · {job.get('salary_status', 'Salary not verified')}")
            st.link_button("Open listing", job["url"])
            if job["url"] in applied_urls:
                st.caption("Already recorded as submitted")
            if st.button("Use this link", key=f"pick_{i}", disabled=not job.get("applyable", True)):
                st.session_state.selected_job_next = job
                st.rerun()

with apply_tab:
    st.subheader("Review and apply")
    if st.session_state.job_queue:
        st.info(f"{len(st.session_state.job_queue)} selected job(s) in your queue. Each application is reviewed and run separately.")
        if st.button("Load next queued job"):
            st.session_state.selected_job_next = st.session_state.job_queue.pop(0)
            st.rerun()
    st.text_input("Job application URL :red[*]", key="application_url", placeholder="https://company.example/jobs/apply")
    st.text_input("Job title", key="job_title")
    profile = st.session_state.saved_profile
    st.markdown("### Attach résumé in TinyFish browser")
    st.caption("Opens a remote TinyFish browser. Use its review link to sign in or navigate to the application form. The app selects your saved résumé in a clear upload field. Complete other fields, check the attachment, and submit there yourself. This browser does not use your TinyFish Vault or saved Browser Context Profile.")
    if st.button("Open TinyFish browser and attach résumé", type="primary", use_container_width=True):
        try:
            browser_url = validate_url(st.session_state.application_url)
            if not allowed_application_url(browser_url, profile):
                raise ValueError("Use a LinkedIn job URL or add this company's official career URL to your profile first.")
            launch_remote_browser(browser_url, os.getenv("TINYFISH_API_KEY", ""))
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(str(exc))
    browser_status = read_status()
    if browser_status.get("state") in ("starting", "waiting_for_form"):
        st.info(browser_status.get("message", "Browser is opening."))
        if not browser_status.get("inspector_url"):
            st.caption("TinyFish may take a short time to start. Click Refresh browser status until the browser link appears.")
    elif browser_status.get("state") == "file_selected":
        st.success(browser_status.get("message", "Résumé selected in the browser."))
    elif browser_status.get("state") == "upload_unverified":
        st.warning(browser_status.get("message", "Check the résumé attachment in your browser."))
    elif browser_status.get("state") == "error":
        st.error(browser_status.get("message", "Browser attachment failed."))
    elif browser_status.get("state") == "closed":
        st.caption(browser_status.get("message", "Browser was closed."))
    inspector_url = browser_status.get("inspector_url", "")
    if browser_status.get("state") in ("starting", "waiting_for_form", "file_selected", "upload_unverified") and inspector_url.startswith("https://"):
        st.link_button("Open TinyFish browser", inspector_url)
        st.caption("Close the TinyFish session when finished to stop browser usage charges.")
    if browser_status.get("state") in ("starting", "waiting_for_form", "file_selected", "upload_unverified", "error"):
        left, right = st.columns(2)
        if left.button("Refresh browser status"):
            st.rerun()
        if browser_status.get("session_id") and right.button("Close TinyFish browser"):
            try:
                close_remote_session(os.getenv("TINYFISH_API_KEY", ""), str(browser_status["session_id"]))
                write_status(str(browser_status["run_id"]), "closed", "TinyFish browser session closed. The app did not click Submit.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not close TinyFish browser: {exc}")
    st.divider()
    st.markdown("### Optional TinyFish form inspection")
    with st.expander("Review saved details"):
        for field, value in profile.items():
            if value:
                st.write(f"**{field.replace('_', ' ').title()}:** {value}")
    if st.button("Draft cover letter from profile"):
        role = st.session_state.job_title or profile.get("role") or "this role"
        st.session_state.cover_letter = (
            f"Dear Hiring Team,\n\nI am interested in {role}. "
            f"{profile.get('bio', '').strip()} My relevant skills include {profile.get('skills', '').strip()}. "
            f"{profile.get('cover_letter_notes', '').strip()}\n\nSincerely,\n{profile.get('first_name', '').strip()} {profile.get('last_name', '').strip()}"
        )
    st.text_area("Cover letter — review and edit", key="cover_letter", height=170)
    with st.expander("Approved answers to special questions"):
        for i, (question, answer) in enumerate(load_answers().items()):
            st.write(f"**{question}** — {answer}")
            if st.button("Forget answer", key=f"forget_{i}"):
                delete_answer(question)
                st.rerun()
        with st.form("new_answer"):
            question = st.text_input("Question")
            answer = st.text_area("Your answer")
            remember = st.form_submit_button("Remember answer")
        if remember:
            if question.strip() and answer.strip():
                try:
                    save_answer(question, answer)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            else:
                st.error("Enter a question and answer.")
    with st.expander("TinyFish sign-in"):
        st.write("If login is needed, sign in through a [TinyFish Browser Context Profile](https://agent.tinyfish.ai), then enter its ID. Connect 1Password or Bitwarden in TinyFish Vault if you want stale sessions repaired. No password is entered here.")
        st.text_input("Browser Context Profile ID", key="tinyfish_profile_id", placeholder="prof_...")
        use_vault = st.checkbox("Use connected TinyFish Vault", key="tinyfish_use_vault")
        st.text_input("Vault credential item ID (recommended)", key="credential_item_id", placeholder="cred:...")
    st.checkbox("Submit after filling", value=False, disabled=True, help="Disabled because the TinyFish Agent API cannot receive the uploaded résumé file.")
    submit = False
    st.warning("TinyFish's form inspection uses a separate Agent browser and cannot attach your résumé. Use the remote TinyFish browser above for the actual application. This optional run will not click Submit.")
    if st.button("Inspect application (no submission)", type="primary", use_container_width=True):
        st.session_state.pop("last_result", None)
        key = os.getenv("TINYFISH_API_KEY", "").strip()
        required_apply = ("first_name", "last_name", "email", "phone", "address", "city", "state", "postal_code", "country", "role", "resume_text", "job_type", "salary_min", "salary_max", "earliest_start")
        if not all(profile.get(field) for field in required_apply):
            st.error("Save a complete profile first.")
        elif profile["job_type"] == "Internship" and not all(profile.get(field) for field in ("branch_of_study", "graduation_year", "highest_qualification")):
            st.error("Save your study details for internship applications first.")
        elif not key:
            st.error("Add TINYFISH_API_KEY to .env and restart.")
        elif not load_resume_info():
            st.error("Save your actual résumé file in the Profile tab before starting an application run.")
        else:
            try:
                url = validate_url(st.session_state.application_url)
                if not allowed_application_url(url, profile):
                    raise ValueError("Use a LinkedIn job URL or add this company's official career URL to your profile first.")
                credential_id = st.session_state.get("credential_item_id", "").strip()
                with st.spinner("TinyFish is working. This can take several minutes…"):
                    result = run_application(
                        profile, url, submit, key,
                        profile_id=st.session_state.get("tinyfish_profile_id", ""),
                        use_vault=use_vault,
                        credential_item_ids=[credential_id] if use_vault and credential_id else None,
                        answers=load_answers(), cover_letter=st.session_state.cover_letter,
                    )
                st.session_state.last_result = result
                save_result(url, st.session_state.job_title or profile["role"], result)
            except Exception as exc:
                st.error(f"Application could not run: {exc}")
    result = st.session_state.get("last_result")
    if result:
        outcome = result["outcome"]
        questions, legacy_manual = split_missing_fields(result.get("missing_fields", []))
        manual_steps = list(dict.fromkeys([*legacy_manual, *(result.get("manual_steps") or [])]))
        resume_not_uploaded = any("resume" in str(step).lower() or "cv" in str(step).lower() or "upload" in str(step).lower() for step in manual_steps)
        legal_acceptance_reported = any(
            any(term in str(field).lower() for term in ("consent", "nda", "privacy statement", "terms and conditions", "declaration"))
            and re.search(r":\s*(yes|checked|accepted|agreed|true)\b", str(field), re.IGNORECASE)
            for field in result.get("filled_fields", [])
        )
        if outcome == "submitted":
            if resume_not_uploaded or legal_acceptance_reported:
                st.warning("Submission reported by the job site — details need verification")
            else:
                st.success("Site-confirmed submission")
        elif outcome == "filled_only":
            st.info("Filled, but not submitted")
        elif outcome == "login_required":
            st.warning("Sign-in required. Set up a TinyFish Browser Context Profile, enter its ID above, then retry.")
        elif outcome == "needs_input":
            st.warning("Answer the questions below and retry." if questions else "Manual steps are needed on the job site.")
        else:
            st.error("Application was not completed")
        st.write(result.get("summary", ""))
        if result.get("confirmation"):
            st.write("**Site confirmation:** " + result["confirmation"])
        if result.get("filled_fields"):
            st.write("**Filled:** " + ", ".join(map(str, result["filled_fields"])))
        if manual_steps:
            st.write(("**Run notes:** " if outcome == "submitted" else "**Manual steps:** ") + ", ".join(map(str, manual_steps)))
            if outcome == "submitted":
                if resume_not_uploaded:
                    st.warning("TinyFish reported a submission, but also reported that it did not upload the résumé file. Check the submitted application on the job site to see whether your résumé is attached. Do not submit a duplicate application.")
            else:
                if resume_not_uploaded:
                    st.info("Your résumé text is already saved. This job site also requires the actual PDF or TXT file to be uploaded. Open the application and attach the file yourself; typing its name here would not upload it.")
                if any(term in str(step).lower() for step in manual_steps for term in ("sign-in", "sign in", "login", "log in", "credential", "authentication")):
                    st.info("Do not enter a password in an answer box. Sign in through a TinyFish Browser Context Profile or connect TinyFish Vault, then retry. If you already did, check that the profile contains a session for this job site.")
            manual_url = result.get("current_url") or st.session_state.application_url
            if manual_url and manual_url.startswith("https://"):
                st.link_button("Open job site to verify the submission" if outcome == "submitted" else "Open job site to complete manually", manual_url)
                if outcome != "submitted":
                    st.caption("This opens a new browser session. The fields the agent filled may need to be entered again.")
        if outcome == "submitted" and legal_acceptance_reported:
            st.warning("TinyFish reported selecting consent or agreement checkboxes. Review what was accepted on the job site before using automatic submission again.")
        if questions:
            st.write("**Questions you can answer:** " + ", ".join(questions))
        if outcome == "needs_input" and questions:
            with st.form("missing_answers"):
                for i, missing in enumerate(questions):
                    st.text_area(str(missing), key=f"missing_{i}")
                save_missing = st.form_submit_button("Remember these answers")
            if save_missing:
                for i, missing in enumerate(questions):
                    value = st.session_state.get(f"missing_{i}", "").strip()
                    if value:
                        try:
                            save_answer(str(missing), value)
                        except ValueError as exc:
                            st.error(str(exc))
                st.success("Answers saved. Retry the application.")
        if outcome == "submitted":
            st.caption("Job-site logout: " + result.get("logout_status", "not_attempted").replace("_", " ") + ". To remove saved sign-in state, delete the site’s domain from your Browser Context Profile in TinyFish.")
        st.caption(f"Run ID: {result.get('run_id') or 'unknown'} · Steps: {result.get('steps', 0)}")
        if st.button("Start another application"):
            st.session_state.clear_application_next = True
            st.rerun()

with results_tab:
    st.subheader("Application results")
    st.caption("Only applications with site confirmation count as submitted.")
    for row in reversed(load_history()):
        with st.container(border=True):
            st.write(f"**{row.get('title') or 'Application'}** · {row.get('outcome', 'unknown').replace('_', ' ').title()}")
            if row.get("url"):
                st.link_button("Open job site", row["url"])
            st.write(row.get("summary", ""))
            if row.get("confirmation"):
                st.caption("Confirmation: " + row["confirmation"])
    if not history:
        st.info("No applications recorded yet.")
