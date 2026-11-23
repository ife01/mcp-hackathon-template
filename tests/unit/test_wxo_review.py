"""Prevent false passes when wxO omits dates, payloads or regional scope."""

import json

from eval.wxo_review import review, tool_evidence


def record(args, payload, answer="", include_response=True):
    call = {"id": "one", "name": "kit:assess_trend", "args": args}
    details = [
        {"type": "tool_calls", "tool_calls": [call]},
        {"type": "tool_call", "tool_call_id": "one", **call},
    ]
    if include_response:
        details.append(
            {
                "type": "tool_response",
                "tool_call_id": "one",
                "content": json.dumps({"data": payload}),
            }
        )
    return {
        "status": "completed",
        "answer": [answer],
        "step_history": [{"step_details": details}],
    }


def test_duplicate_trace_views_count_as_one_call():
    assert len(tool_evidence(record({}, {}))) == 1


def test_null_cutoff_does_not_pass_dated_question():
    result = review(record({"as_of": None}, {}), "2026-10-31")
    assert not result["checks"]["cutoff_arguments"]


def test_missing_tool_response_is_not_a_pass():
    result = review(
        record({"as_of": "2026-10-31"}, {}, include_response=False), "2026-10-31"
    )
    assert not result["automated_checks_pass"]


def test_nested_later_observation_fails_but_retrieval_date_does_not():
    data = {
        "retrieved_at": "2026-11-23T00:00:00Z",
        "series": [{"week_ending": "2026-10-31"}],
    }
    assert review(record({"as_of": "2026-10-31"}, data), "2026-10-31")["checks"][
        "observations_within_cutoff"
    ]
    data["series"].append({"week_ending": "2026-11-14"})
    assert not review(record({"as_of": "2026-10-31"}, data), "2026-10-31")["checks"][
        "observations_within_cutoff"
    ]


def test_missing_trace_does_not_pass_vacuously():
    assert not review({"status": "completed"}, "2026-10-31")["automated_checks_pass"]


def test_regional_scan_rejects_out_of_region_missing_state():
    data = record(
        {"as_of": "2026-10-31", "hhs_region": 4},
        {"n_jurisdictions_scanned": 8, "unavailable_jurisdictions": ["AR"]},
    )
    for d in data["step_history"][0]["step_details"]:
        if "name" in d:
            d["name"] = "find_jurisdictions_with_rising_activity"
        for call in d.get("tool_calls", []):
            call["name"] = "find_jurisdictions_with_rising_activity"
    assert not review(data, "2026-10-31", 4)["checks"]["region_payload_scope"]


def test_error_paraphrase_requires_review():
    data = record(
        {"as_of": "2015-01-01"},
        {"error": "invalid_input", "message": "Application limit only."},
        "The dataset began in 2020.",
    )
    assert not review(data, "2015-01-01")["checks"]["error_message_preserved"]


def test_exact_error_message_passes_without_observations():
    data = record(
        {"as_of": "2015-01-01"},
        {"error": "invalid_input", "message": "Application limit only."},
        "Application limit only.",
    )
    result = review(data, "2015-01-01")
    assert result["automated_checks_pass"]
    assert result["checks"]["observations_within_cutoff"] is None
    assert result["semantic_answer_review_required"]


def test_latest_question_does_not_require_a_benchmark_date():
    data = record({}, {"week_ending": "2026-11-14"})
    assert review(data, None)["checks"]["cutoff_arguments"]
