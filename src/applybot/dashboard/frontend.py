"""Streamlit dashboard frontend for ApplyBot."""

from __future__ import annotations

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"


def _get(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Make a GET request to the API."""
    try:
        resp = httpx.get(f"{API_BASE}{endpoint}", params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def _post(endpoint: str, json_data: dict | None = None) -> dict | None:
    """Make a POST request to the API."""
    try:
        resp = httpx.post(f"{API_BASE}{endpoint}", json=json_data, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def _put(endpoint: str, json_data: dict | None = None) -> dict | None:
    """Make a PUT request to the API."""
    try:
        resp = httpx.put(f"{API_BASE}{endpoint}", json=json_data, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def main() -> None:
    st.set_page_config(page_title="ApplyBot Dashboard", page_icon="🤖", layout="wide")
    st.title("🤖 ApplyBot Dashboard")

    page = st.sidebar.radio(
        "Navigation",
        ["Overview", "Job Queue", "Applications", "Profile"],
    )

    if page == "Overview":
        _page_overview()
    elif page == "Job Queue":
        _page_job_queue()
    elif page == "Applications":
        _page_applications()
    elif page == "Profile":
        _page_profile()


def _page_overview() -> None:
    """Dashboard overview with stats."""
    st.header("Dashboard Overview")

    summary = _get("/dashboard/summary")
    if not summary:
        st.warning("Could not load dashboard summary. Is the API running?")
        st.code("Start the API with: uvicorn applybot.dashboard.api:app --reload")
        return

    # Stats cards
    col1, col2, col3, col4 = st.columns(4)

    jobs = summary.get("jobs", {})
    apps = summary.get("applications", {})

    col1.metric("Total Jobs Found", jobs.get("total", 0))
    col2.metric("New Jobs", jobs.get("new", 0))
    col3.metric("Applications", apps.get("total", 0))
    col4.metric("Interviews", apps.get("interview", 0))

    # Pipeline
    st.subheader("Pipeline")
    pipeline_data = {
        "New Jobs": jobs.get("new", 0),
        "Reviewing": jobs.get("reviewing", 0),
        "Approved": jobs.get("approved", 0),
        "Applied": jobs.get("applied", 0),
    }
    st.bar_chart(pipeline_data)

    # Application statuses
    if apps.get("total", 0) > 0:
        st.subheader("Application Statuses")
        app_data = {k: v for k, v in apps.items() if k != "total"}
        st.bar_chart(app_data)


def _page_job_queue() -> None:
    """Job queue — review and approve/skip discovered jobs."""
    st.header("Job Queue")

    # Filters
    col1, col2 = st.columns(2)
    status_filter = col1.selectbox(
        "Status", ["new", "approved", "reviewing", "skipped", "applied", "rejected", ""]
    )
    min_score = col2.slider("Min Relevance Score", 0, 100, 50)

    params = {"limit": 100}
    if status_filter:
        params["status"] = status_filter
    if min_score > 0:
        params["min_score"] = min_score

    jobs = _get("/jobs", params)
    if not jobs:
        st.info("No jobs found matching your filters.")
        return

    st.write(f"**{len(jobs)} jobs found**")

    for job in jobs:
        with st.expander(
            f"**{job['title']}** at {job['company']} — Score: {job.get('relevance_score', 'N/A')}"
        ):
            st.write(f"**Location:** {job['location']}")
            st.write(f"**Source:** {job['source']}")
            st.write(f"**Status:** {job['status']}")
            if job.get("relevance_reasoning"):
                st.write(f"**Match reasoning:** {job['relevance_reasoning']}")
            if job.get("url"):
                st.markdown(f"[View Job Posting]({job['url']})")

            st.text_area(
                "Description",
                job.get("description", "")[:2000],
                height=150,
                key=f"desc_{job['id']}",
                disabled=True,
            )

            if job["status"] == "new":
                col1, col2 = st.columns(2)
                if col1.button("✅ Approve", key=f"approve_{job['id']}"):
                    result = _post(f"/jobs/{job['id']}/approve")
                    if result:
                        st.success("Job approved!")
                        st.rerun()
                if col2.button("⏭️ Skip", key=f"skip_{job['id']}"):
                    result = _post(f"/jobs/{job['id']}/skip")
                    if result:
                        st.info("Job skipped.")
                        st.rerun()


def _page_applications() -> None:
    """Application review page."""
    st.header("Applications")

    status_filter = st.selectbox(
        "Status",
        [
            "",
            "draft",
            "ready_for_review",
            "approved",
            "submitted",
            "received",
            "interview",
            "offer",
            "rejected",
            "withdrawn",
        ],
    )

    params = {"limit": 100}
    if status_filter:
        params["status"] = status_filter

    apps = _get("/applications", params)
    if not apps:
        st.info("No applications found.")
        return

    st.write(f"**{len(apps)} applications**")

    for application in apps:
        job = _get(f"/jobs/{application['job_id']}")
        job_title = (
            f"{job['title']} at {job['company']}"
            if job
            else f"Job #{application['job_id']}"
        )

        with st.expander(f"**{job_title}** — Status: {application['status']}"):
            st.write(f"**Created:** {application['created_at']}")
            if application.get("submitted_at"):
                st.write(f"**Submitted:** {application['submitted_at']}")

            # Cover letter
            if application.get("cover_letter"):
                st.subheader("Cover Letter")
                st.text_area(
                    "Cover letter",
                    application["cover_letter"],
                    height=200,
                    key=f"cover_{application['id']}",
                    disabled=True,
                )

            # Answers
            if application.get("answers"):
                st.subheader("Application Answers")
                for q, a in application["answers"].items():
                    st.write(f"**Q:** {q}")
                    st.write(f"**A:** {a}")
                    st.divider()

            # Resume path
            if application.get("tailored_resume_path"):
                st.write(f"**Tailored resume:** {application['tailored_resume_path']}")

            # Actions
            if application["status"] == "ready_for_review":
                col1, col2 = st.columns(2)
                if col1.button("✅ Approve", key=f"app_approve_{application['id']}"):
                    result = _post(
                        f"/applications/{application['id']}/review",
                        {"status": "approved"},
                    )
                    if result:
                        st.success("Application approved!")
                        st.rerun()
                if col2.button(
                    "🔄 Back to Draft", key=f"app_draft_{application['id']}"
                ):
                    result = _post(
                        f"/applications/{application['id']}/review",
                        {"status": "draft"},
                    )
                    if result:
                        st.info("Sent back to draft.")
                        st.rerun()


def _page_profile() -> None:
    """Profile editor page."""
    st.header("Profile")

    profile = _get("/profile")

    if profile is None:
        st.info("No profile yet. Create one below.")
        profile = {}

    with st.form("profile_form"):
        name = st.text_input("Name", profile.get("name", ""))
        email = st.text_input("Email", profile.get("email", ""))
        summary = st.text_area("Summary", profile.get("summary", ""), height=100)

        submitted = st.form_submit_button("Save Profile")
        if submitted:
            result = _put(
                "/profile", {"name": name, "email": email, "summary": summary}
            )
            if result:
                st.success("Profile updated!")
                st.rerun()

    # Show full profile data
    if profile:
        with st.expander("Full Profile Data"):
            st.json(profile)


if __name__ == "__main__":
    main()
