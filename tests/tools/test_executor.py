import pytest

from vaultkit.tools.executor import ToolExecutor
from vaultkit.errors.exceptions import (
    ApprovalRequiredError,
    DeniedError,
    ValidationError,
    QueuedError,
)


class DummyClient:
    def __init__(self):
        self._datasets = []
        self._execute_result = None
        self._poll_result = None
        self._fetch_result = None

    def datasets(self, **kwargs):
        return self._datasets

    def execute(self, **kwargs):
        if isinstance(self._execute_result, Exception):
            raise self._execute_result
        return self._execute_result

    def poll_request(self, **kwargs):
        return self._poll_result

    def fetch(self, **kwargs):
        return self._fetch_result


class DummyDataset:
    def __init__(self, dataset, datasource, visibility=None):
        self.dataset = dataset
        self.datasource = datasource
        self.visibility = visibility


class DummyFetch:
    def __init__(self, rows, masked_fields=None):
        self.data = rows
        self.row_count = len(rows)
        self.masked_fields = masked_fields or []


class DummyQueryResult:
    def __init__(self, status, grant_ref=None, reason=None):
        self.status = status
        self.grant_ref = grant_ref
        self.reason = reason

    @property
    def is_granted(self):
        return self.status == "granted"

    @property
    def is_denied(self):
        return self.status == "denied"


@pytest.fixture
def executor():
    client = DummyClient()
    return ToolExecutor(client, default_purpose="test", default_requester_region="US"), client


def test_unknown_tool(executor):
    executor, _ = executor

    res = executor.execute("bad_tool", {})

    assert res["status"] == "unknown_tool"


def test_discover(executor):
    executor, client = executor

    client._datasets = [
        DummyDataset("users", "pg", "allow"),
        DummyDataset("payments", "pg", "deny"),
    ]

    res = executor.execute("vaultkit_discover", {})

    assert res["status"] == "ok"
    assert res["count"] == 2
    assert res["datasets"][0]["visibility"] == "accessible"
    assert res["datasets"][1]["visibility"] == "not accessible"


def test_query_success(executor):
    executor, client = executor

    client._execute_result = DummyFetch([{"id": 1}])

    res = executor.execute("vaultkit_query", {"dataset": "users"})

    assert res["status"] == "ok"
    assert res["row_count"] == 1
    assert res["data"] == [{"id": 1}]


def test_query_with_masked_fields(executor):
    executor, client = executor

    client._execute_result = DummyFetch(
        [{"id": 1}],
        masked_fields=["email"],
    )

    res = executor.execute("vaultkit_query", {"dataset": "users"})

    assert "note" in res
    assert "email" in res["note"]


def test_query_missing_dataset(executor):
    executor, _ = executor

    res = executor.execute("vaultkit_query", {})

    assert res["status"] == "validation_error"


def test_check_approval_granted(executor):
    executor, client = executor

    client._poll_result = DummyQueryResult("granted", grant_ref="g1")
    client._fetch_result = DummyFetch([{"id": 1}])

    res = executor.execute("vaultkit_check_approval", {"request_id": "r1"})

    assert res["status"] == "approved"
    assert res["row_count"] == 1


def test_check_approval_denied(executor):
    executor, client = executor

    client._poll_result = DummyQueryResult("denied", reason="nope")

    res = executor.execute("vaultkit_check_approval", {"request_id": "r1"})

    assert res["status"] == "denied"
    assert res["reason"] == "nope"


def test_check_approval_pending(executor):
    executor, client = executor

    client._poll_result = DummyQueryResult("queued")

    res = executor.execute("vaultkit_check_approval", {"request_id": "r1"})

    assert res["status"] == "pending"


def test_denied_error_translation(executor):
    executor, client = executor

    client._execute_result = DeniedError("blocked", policy_id="p1")

    res = executor.execute("vaultkit_query", {"dataset": "users"})

    assert res["status"] == "denied"
    assert "policy_id=p1" in res["error"]


def test_approval_required_translation(executor):
    executor, client = executor

    client._execute_result = ApprovalRequiredError("need approval", request_id="r1")

    res = executor.execute("vaultkit_query", {"dataset": "users"})

    assert res["status"] == "pending_approval"
    assert res["request_id"] == "r1"


def test_validation_error_translation(executor):
    executor, client = executor

    client._execute_result = ValidationError("bad query")

    res = executor.execute("vaultkit_query", {"dataset": "users"})

    assert res["status"] == "validation_error"


def test_queued_error_translation(executor):
    executor, client = executor

    client._execute_result = QueuedError("queued", request_id="r1")

    res = executor.execute("vaultkit_query", {"dataset": "users"})

    assert res["status"] == "queued"
    assert res["request_id"] == "r1"
