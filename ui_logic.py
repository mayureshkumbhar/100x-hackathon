"""Pure draft validation and fixed examples. No network or session storage."""
import ipaddress
import re
from urllib.parse import urlsplit


def validate_draft(url, in_key, out_key, rows):
    try:
        parsed = urlsplit((url or "").strip())
        host = parsed.hostname or ""
        if len(url) > 2048 or parsed.scheme != "https" or not host or parsed.username is not None or parsed.password is not None:
            raise ValueError
        if parsed.query or parsed.fragment or parsed.port not in (None, 443):
            raise ValueError
        if host.lower() == "localhost" or host.lower().endswith((".local", ".localhost", ".internal")):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or not re.fullmatch(r"[a-zA-Z0-9.-]+", host):
                raise ValueError
        else:
            if not address.is_global:
                raise ValueError
    except (ValueError, TypeError, AttributeError):
        return "Enter a public HTTPS endpoint without credentials, query parameters or a fragment (port 443 only)."
    for label, key in (("Request", in_key), ("Answer", out_key)):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", key):
            return f"{label} field must be a simple field name, such as input or output."
    if not isinstance(rows, list) or len(rows) > 10:
        return "Provide up to ten rows."
    count = 0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            return f"Row {index}: expected input, answer criteria and checks."
        if any(value is not None and not isinstance(value, str) for value in row):
            return f"Row {index}: use text in each column."
        fields = [(value or "").strip() for value in row]
        if not any(fields):
            continue
        if not all(fields):
            return f"Row {index}: fill in all three columns, or leave the whole row blank."
        if any(len(value) > 10000 for value in fields):
            return f"Row {index}: each cell must be at most 10,000 characters."
        for check in fields[2].split(";"):
            check = check.strip()
            if check in {"has_number", "has_baseline"} or re.fullmatch(r"max_words:[1-9][0-9]{0,3}", check):
                continue
            if check.startswith("judge:") and check[6:].strip():
                continue
            return f"Row {index}: unsupported or empty check. Use max_words:300, has_number, has_baseline or judge:criterion."
        count += 1
    if not count:
        return "Add at least one complete golden pair."
    return (f"{count} of 10 golden pairs validated. "
            + ("Draft complete. " if count == 10 else "Add the remaining pairs before real evaluation. ")
            + "No request sent or data saved. AI judging remains unavailable.")


def inspect_case(case_id):
    if case_id == "GP-01":
        return (
            "We approve invoices by email and it takes days",
            "Identifies the approval bottleneck and gives a measurable next step",
            "Centralize invoice approvals and notify the reviewer automatically.",
            [["max_words:300", "Pass", "9 words; limit 300"],
             ["has_number", "Fail", "No numeric target or baseline in the sample answer"],
             ["judge:names the real bottleneck", "Not evaluated", "AI judge has not been calibrated"]],
        )
    if case_id == "GP-02":
        return (
            "Our onboarding is slow. Suggest a measurable first experiment.",
            "Proposes an experiment with a baseline and target",
            "Measure baseline onboarding time over 7 days. Test a checklist and target a 20% reduction.",
            [["has_number", "Pass", "Includes 7 days and 20%"],
             ["has_baseline", "Pass", "Explicitly measures baseline onboarding time"]],
        )
    return "", "", "", []


def load_demo():
    import gradio as gr
    return (
        "### Sample: 1 passed · 1 failed\nTwo predefined examples; your draft was not executed. "
        "The AI check is not evaluated. Open Failures to inspect each answer.",
        [["GP-01 · Invoice approvals", "Fail", "has_number"], ["GP-02 · Onboarding", "Pass", "None"]],
        gr.update(choices=[("GP-01 · Invoice approvals", "GP-01"), ("GP-02 · Onboarding", "GP-02")], value="GP-01"),
        gr.update(choices=["Sample run 1", "Sample run 2"], value="Sample run 1"),
        gr.update(choices=["Sample run 1", "Sample run 2"], value="Sample run 2"),
        *inspect_case("GP-01"),
    )


def compare_runs(earlier, later):
    valid = {"Sample run 1", "Sample run 2"}
    if earlier not in valid or later not in valid:
        return "Load the sample evaluation and select two runs first.", []
    if earlier == later:
        return "Choose two different runs.", []
    if earlier != "Sample run 1":
        return "Select Sample run 1 as earlier and Sample run 2 as later.", []
    return ("Sample only: 1 fixed · 0 regressions · 1 unchanged. AI checks excluded.",
            [["GP-01 · Invoice approvals", "Fail", "Pass", "Fixed"],
             ["GP-02 · Onboarding", "Pass", "Pass", "Unchanged"]])
