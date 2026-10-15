"""Research timestamps use Beijing time; durations and Unix epochs stay unchanged."""

import json
from datetime import datetime, timedelta, timezone

BEIJING = timezone(timedelta(hours=8))
TIME_FIELDS = {
    'created_at', 'occurred_at', 'received_at', 'started_at', 'ended_at',
    'first_login_at', 'last_login_at', 'last_seen_at', 'consented_at',
    'client_started_at', 'last_activity_at', 'server_started_at',
    'server_received_at', 'generated_at',
}


def beijing_now():
    return datetime.now(BEIJING).isoformat(timespec='milliseconds')


def beijing_timestamp(value):
    if not isinstance(value, str) or not value:
        return value
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return value
    # Legacy server timestamps were UTC; do not depend on the server's local zone.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(BEIJING).isoformat(timespec='milliseconds')


def normalise_record_times(value):
    """Convert named timestamp fields, including JSON columns, without editing prose."""
    if isinstance(value, list):
        return [normalise_record_times(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in TIME_FIELDS:
            result[key] = beijing_timestamp(item)
        elif key in {'payload_json', 'metadata_json', 'client_metadata_json'} and isinstance(item, str):
            try:
                result[key] = json.dumps(normalise_record_times(json.loads(item)), ensure_ascii=False)
            except (ValueError, TypeError):
                result[key] = item
        else:
            result[key] = normalise_record_times(item)
    return result
