import pytest
from unittest.mock import MagicMock
from app.main import handle_case_sync
from app.drift_detector import detect_drift

def test_drift_detection():
    v4_state = {"id": "1", "updated": 100}
    v5_state = {"id": "1", "updated": 100}
    assert not detect_drift(v4_state, v5_state)

    v5_state_newer = {"id": "1", "updated": 200}
    assert detect_drift(v4_state, v5_state_newer)

def test_sync_newer_v4_event():
    # Mock OpenSearch
    os_client = MagicMock()
    # v5 has old state
    os_client.get.return_value = {"_source": {"updated_at": 1000}}

    producer = MagicMock()

    event = {
        "tenant_id": "T1",
        "payload": {
            "case_id": "C1",
            "updated_at": 2000,
            "title": "New Title"
        }
    }

    handle_case_sync(event, os_client, producer)

    # Should call index (update)
    os_client.index.assert_called_once()
    args, kwargs = os_client.index.call_args
    assert kwargs['body']['title'] == "New Title"

def test_sync_conflict_v5_newer():
    # Mock OpenSearch
    os_client = MagicMock()
    # v5 has NEWER state
    os_client.get.return_value = {"_source": {"updated_at": 3000}}

    producer = MagicMock()

    event = {
        "tenant_id": "T1",
        "payload": {
            "case_id": "C1",
            "updated_at": 2000, # Older
            "title": "Old Title"
        }
    }

    handle_case_sync(event, os_client, producer)

    # Should NOT call index
    os_client.index.assert_not_called()
    # Should send drift log
    producer.send.assert_called_once()
    args, _ = producer.send.call_args
    assert args[0] == "bridge.drift.log.v1"
