import os
import json
import logging
from kafka import KafkaProducer

logger = logging.getLogger("kafka-publisher")

def get_producer():
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:29092")
    protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")

    kwargs = {
        "bootstrap_servers": bootstrap,
        "security_protocol": protocol,
        "value_serializer": lambda v: json.dumps(v).encode('utf-8'),
        "key_serializer": lambda v: v.encode('utf-8') if v else None
    }

    if protocol == "SSL":
        kwargs["ssl_cafile"] = os.getenv("KAFKA_SSL_CAFILE")
        kwargs["ssl_certfile"] = os.getenv("KAFKA_SSL_CERTFILE")
        kwargs["ssl_keyfile"] = os.getenv("KAFKA_SSL_KEYFILE")

    return KafkaProducer(**kwargs)

def publish_event(producer, row):
    """
    Publishes a single outbox row.
    Key: tenant_id:aggregate_type:aggregate_id
    Topic: bridge.v4.{event_type} (mapped)
    """
    event_type = row['event_type']
    tenant_id = row['tenant_id']
    agg_type = row['aggregate_type']
    agg_id = row['aggregate_id']
    payload = row['payload']

    # Construct Topic
    # Default mapping: bridge.v4.case.sync.v1
    topic = f"bridge.v4.{event_type}"

    # Construct Key
    key = f"{tenant_id}:{agg_type}:{agg_id}"

    # Envelope
    envelope = {
        "event_id": str(row['outbox_id']), # Deterministic
        "type": event_type,
        "tenant_id": tenant_id,
        "trace_id": row.get('trace_id'),
        "timestamp": row['created_at'],
        "schema_version": "1.0",
        "payload": payload
    }

    future = producer.send(topic, key=key, value=envelope)
    return future
