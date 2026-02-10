# v5-Internal Core Platform

## Mission
Decouple high-value SOC functions from the legacy TheHive 3/4 monolith using the Strangler Fig Pattern.

## Architecture
- **Event Spine**: Redpanda (Kafka-compatible) for high-throughput, persistent event streaming.
- **Ingestion Service**: Stateless, Python FastAPI service for validating and publishing alerts.
- **Observability**: Structured logs, metrics, and distributed tracing.

## Directory Structure
- `event-spine/`: Infrastructure configuration for the event bus.
- `alert-ingestion-service/`: Source code for the ingestion API.
