import pytest
import hashlib
import json
from unittest.mock import MagicMock
from app.main import handle_case_sync, handle_alert_sync
# We import the drift checker logic (in a real app this would be a shared module)
# Since the script is standalone, we just verify the inline drift detection in main.py
# which is timestamp based as per B1_2 requirement.
# B1_4 "Hash Based" is for the nightly job script.

def test_sync_newer_v4_event():
    # Mock OpenSearch
    os_client = MagicMock()
    # v5 has old state
    os_client.get.return_value = {"_source": {"updated_at": 1000}}

    producer = MagicMock()

    event = {
        "tenant_id": "T1",
        "type": "case.sync.v1",
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
        "type": "case.sync.v1",
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

def test_alert_sync():
    os_client = MagicMock()
    os_client.get.side_effect = Exception("Not Found") # Simulate new alert

    producer = MagicMock()
    event = {
        "tenant_id": "T1",
        "type": "alert.sync.v1",
        "payload": {
            "alert_id": "A1",
            "title": "New Alert",
            "updated_at": 5000
        }
    }

    handle_alert_sync(event, os_client, producer)
    os_client.index.assert_called_once()
