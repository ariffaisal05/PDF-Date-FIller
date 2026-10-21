"""Optional aggregate usage analytics backed by Supabase Postgres."""

import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

import altair as alt
import streamlit as st


def _config():
    try:
        secrets = st.secrets
        return (
            secrets.get("SUPABASE_URL", "").rstrip("/"),
            secrets.get("SUPABASE_SECRET_KEY", secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")),
            secrets.get("ANALYTICS_PASSWORD", ""),
        )
    except Exception:
        return "", "", ""


def ready():
    url, key, _ = _config()
    return bool(url and key)


def _request(method, path, payload=None, row_range=None):
    url, key, _ = _config()
    if not url or not key:
        return None

    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    if row_range:
        headers["Range"] = row_range
    request = urllib.request.Request(
        f"{url}/rest/v1/{path}", data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            body = response.read()
            return json.loads(body) if body else []
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def _log_event(event_type, session_id, properties=None):
    _request(
        "POST",
        "analytics_events",
        {
            "event_type": event_type,
            "session_id": session_id,
            "properties": properties or {},
        },
    )


def log_session(session_id):
    _log_event("session", session_id)


def log_job(session_id, files, elapsed_seconds):
    languages = Counter()
    methods = Counter()
    errors = Counter()
    successes = 0

    for item in files:
        result = item["result"]
        methods[result.get("detection_method", "Unknown")] += 1
        if result.get("success"):
            successes += 1
            language = "English" if result.get("detected_text") == "Today" else "Indonesian"
            languages[language] += 1
        else:
            message = result.get("message", "")
            reason = "date_label_not_found" if message.startswith("Could not find") else "processing_error"
            errors[reason] += 1

    _log_event(
        "job",
        session_id,
        {
            "batch_size": len(files),
            "success_count": successes,
            "failure_count": len(files) - successes,
            "job_success": successes == len(files),
            "duration_seconds": round(elapsed_seconds, 3),
            "detection_methods": dict(methods),
            "language_counts": dict(languages),
            "error_counts": dict(errors),
        },
    )


def _load_events(days):
    params = {
        "select": "event_type,created_at,properties",
        "order": "created_at.desc",
        "limit": "1000",
    }
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        params["created_at"] = f"gte.{since.isoformat()}"
    query = urllib.parse.urlencode(params)

    events = []
    for offset in range(0, 10000, 1000):
        page = _request(
            "GET",
            f"analytics_events?{query}",
            row_range=f"{offset}-{offset + 999}",
        )
        if page is None:
            return None
        events.extend(page)
        if len(page) < 1000:
            break
    return events


def show_dashboard():
    _, _, password = _config()
    if not password:
        st.info("Add `ANALYTICS_PASSWORD` to Streamlit secrets to enable the private dashboard.")
        return

    if not st.session_state.get("analytics_authenticated"):
        with st.form("analytics_login"):
            entered = st.text_input("Admin password", type="password")
            submitted = st.form_submit_button("Unlock analytics")
        if submitted and hmac.compare_digest(entered, password):
            st.session_state.analytics_authenticated = True
            st.rerun()
        if submitted:
            st.error("Incorrect password.")
        return

    period = st.selectbox("Time range", ["7 days", "30 days", "90 days", "All time"])
    days = {"7 days": 7, "30 days": 30, "90 days": 90}.get(period)
    events = _load_events(days)
    if events is None:
        st.error("Could not load analytics. Check your Supabase URL, key, and table setup.")
        return
    if len(events) == 10000:
        st.caption("Showing the latest 10,000 events. Choose a shorter range for recent data.")

    sessions = [event for event in events if event["event_type"] == "session"]
    jobs = [event["properties"] for event in events if event["event_type"] == "job"]
    total_files = sum(job.get("batch_size", 0) for job in jobs)
    successes = sum(job.get("success_count", 0) for job in jobs)
    failures = sum(job.get("failure_count", 0) for job in jobs)
    successful_jobs = sum(job.get("job_success", False) for job in jobs)
    durations = [job.get("duration_seconds", 0) for job in jobs]
    batches = [job.get("batch_size", 0) for job in jobs]

    columns = st.columns(4)
    columns[0].metric("App sessions (approx. visits)", len(sessions))
    columns[1].metric("Processing jobs", len(jobs))
    columns[2].metric("PDFs processed", total_files)
    columns[3].metric("Successful PDFs", successes, delta=f"{failures} failed")

    second_row = st.columns(4)
    second_row[0].metric("Fully successful jobs", f"{successful_jobs} / {len(jobs)}")
    second_row[1].metric("Average job time", f"{sum(durations) / len(durations):.1f}s" if durations else "—")
    second_row[2].metric("Average batch size", f"{sum(batches) / len(batches):.1f}" if batches else "—")
    second_row[3].metric("Largest batch", max(batches, default=0))

    daily = {}
    languages = Counter()
    methods = Counter()
    errors = Counter()
    for event in events:
        day = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")).date().isoformat()
        counts = daily.setdefault(day, {"Date": day, "Sessions": 0, "Jobs": 0})
        if event["event_type"] == "session":
            counts["Sessions"] += 1
        elif event["event_type"] == "job":
            counts["Jobs"] += 1
            properties = event["properties"]
            languages.update(properties.get("language_counts", {}))
            methods.update(properties.get("detection_methods", {}))
            errors.update(properties.get("error_counts", {}))

    st.subheader("Sessions and jobs over time")
    timeline = [daily[day] for day in sorted(daily)]
    if timeline:
        chart_data = alt.Data(values=timeline)
        chart = (
            alt.Chart(chart_data)
            .transform_fold(["Sessions", "Jobs"], as_=["Metric", "Count"])
            .encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Count:Q", title="Count", scale=alt.Scale(zero=True)),
                color=alt.Color(
                    "Metric:N",
                    title=None,
                    scale=alt.Scale(
                        domain=["Sessions", "Jobs"],
                        range=["#60A5FA", "#F97316"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("Date:T", title="Date"),
                    alt.Tooltip("Metric:N", title="Series"),
                    alt.Tooltip("Count:Q", title="Count"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(
            chart.mark_line(strokeWidth=3) + chart.mark_circle(size=140),
            use_container_width=True,
        )
        st.dataframe(timeline, hide_index=True, use_container_width=True)
    else:
        st.caption("No activity recorded in this time range yet.")

    left, right = st.columns(2)
    with left:
        st.subheader("Detection method and language")
        st.write({"Detection methods": dict(methods), "Languages": dict(languages)})
        if not methods.get("OCR"):
            st.caption("No OCR usage recorded in this time range.")
    with right:
        st.subheader("Failure categories")
        st.write(dict(errors) or {"No failures recorded": 0})
    if durations:
        st.caption(f"Slowest processing job: {max(durations):.1f}s")
