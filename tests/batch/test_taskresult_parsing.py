import pytest
import json

from django_celery_results.models import TaskResult
from VVweb.web.admin import parse_result


@pytest.mark.django_db
class TestTaskResultParsing:
    """
    Tests for parsing TaskResult.result into a clean structure
    for admin display.

    Covers:
    - SUCCESS (normal return values)
    - FAILURE (TaskFailure with structured payload)
    - SYSTEM failures (unexpected exceptions)
    - malformed input safety
    """

    # --------------------------------------------------
    # SUCCESS case
    # --------------------------------------------------
    def test_parse_success_result(self):
        payload = {
            "status": "success",
            "task_id": "test-success",
            "user_id": 1,
            "email": "user@example.com",
            "result": ["row1", "row2"],
        }

        tr = TaskResult.objects.create(
            task_id="test-success",
            status="SUCCESS",
            result=json.dumps(payload),
        )

        parsed = parse_result(tr)

        assert parsed["status"] == "success"
        assert parsed["user_id"] == 1
        assert parsed["email"] == "user@example.com"
        assert parsed["result"] == ["row1", "row2"]

    # --------------------------------------------------
    # FAILURE case (TaskFailure payload)
    # --------------------------------------------------
    def test_parse_failure_taskfailure_payload(self):
        payload = {
            "status": "error",
            "task_id": "test-failure",
            "user_id": 42,
            "email": "fail@example.com",
            "error": "VariantValidatorError: Validation error",
        }

        celery_wrapped = {
            "exc_type": "TaskFailure",
            "exc_message": [json.dumps(payload)],
        }

        tr = TaskResult.objects.create(
            task_id="test-failure",
            status="FAILURE",
            result=json.dumps(celery_wrapped),
        )

        parsed = parse_result(tr)

        assert parsed["status"] == "error"
        assert parsed["user_id"] == 42
        assert parsed["email"] == "fail@example.com"
        assert "Validation error" in parsed["error"]

    # --------------------------------------------------
    # SYSTEM failure (no structured payload)
    # --------------------------------------------------
    def test_parse_unexpected_system_failure(self):
        celery_wrapped = {
            "exc_type": "ValueError",
            "exc_message": ["Something unexpected happened"],
        }

        tr = TaskResult.objects.create(
            task_id="test-system-failure",
            status="FAILURE",
            result=json.dumps(celery_wrapped),
        )

        parsed = parse_result(tr)

        # Should NOT invent user_id
        assert "user_id" not in parsed

        # Should preserve original structure
        assert parsed["exc_type"] == "ValueError"
        assert parsed["exc_message"][0] == "Something unexpected happened"

    # --------------------------------------------------
    # Safety: malformed JSON
    # --------------------------------------------------
    def test_parse_result_handles_invalid_json(self):
        tr = TaskResult.objects.create(
            task_id="test-invalid-json",
            status="FAILURE",
            result="not-json",
        )

        parsed = parse_result(tr)

        assert parsed == {}

    # --------------------------------------------------
    # Safety: empty/null result
    # --------------------------------------------------
    def test_parse_result_handles_empty(self):
        tr = TaskResult.objects.create(
            task_id="test-empty",
            status="SUCCESS",
            result=None,
        )

        parsed = parse_result(tr)

        assert parsed == {}

    # --------------------------------------------------
    # Edge case: nested but not TaskFailure
    # --------------------------------------------------
    def test_parse_result_ignores_non_json_exc_message(self):
        celery_wrapped = {
            "exc_type": "RuntimeError",
            "exc_message": ["not json string"],
        }

        tr = TaskResult.objects.create(
            task_id="test-non-json-exc",
            status="FAILURE",
            result=json.dumps(celery_wrapped),
        )

        parsed = parse_result(tr)

        # Should fall back safely
        assert parsed["exc_type"] == "RuntimeError"

