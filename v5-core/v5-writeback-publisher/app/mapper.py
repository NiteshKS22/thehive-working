def map_case_event(event):
    """
    Maps v5 case event to v4 writeback payload.
    """
    payload = event.get('payload', {})

    # Strip fields not in v4
    # Map status

    return {
        "case_id": payload.get('case_id'),
        "title": payload.get('title'),
        "description": payload.get('description'),
        "severity": payload.get('severity'),
        "status": payload.get('status'),
        "updated_at": payload.get('updated_at'),
        "updated_by": payload.get('updated_by')
    }
