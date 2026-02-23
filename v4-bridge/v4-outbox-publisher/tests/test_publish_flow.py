import unittest
from unittest.mock import MagicMock
from app.publisher import publish_event

class TestPublisher(unittest.TestCase):
    def test_publish_envelope(self):
        producer = MagicMock()
        future = MagicMock()
        producer.send.return_value = future

        row = {
            'outbox_id': 'uuid-1',
            'tenant_id': 'T1',
            'aggregate_type': 'CASE',
            'aggregate_id': 'C1',
            'event_type': 'case.sync.v1',
            'payload': {'foo': 'bar'},
            'trace_id': 'trace-1',
            'created_at': 1000
        }

        publish_event(producer, row)

        producer.send.assert_called_once()
        args, kwargs = producer.send.call_args
        topic = args[0]
        key = kwargs['key']
        value = kwargs['value']

        self.assertEqual(topic, 'bridge.v4.case.sync.v1')
        self.assertEqual(key, 'T1:CASE:C1')
        self.assertEqual(value['event_id'], 'uuid-1')
        self.assertEqual(value['tenant_id'], 'T1')
        self.assertEqual(value['payload'], {'foo': 'bar'})

if __name__ == '__main__':
    unittest.main()
