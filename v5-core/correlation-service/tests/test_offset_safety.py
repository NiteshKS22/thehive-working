import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

# Add app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

# Setup environment
os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:9092'
os.environ['REDIS_HOST'] = 'localhost'
os.environ['REDIS_PORT'] = '6379'
os.environ['RULES_FILE'] = 'rules.yaml'

# Mock kafka
sys.modules['kafka'] = MagicMock()
sys.modules['kafka.errors'] = MagicMock()

import main

class TestOffsetSafety(unittest.TestCase):

    @patch('main.KafkaConsumer')
    @patch('main.KafkaProducer')
    @patch('main.Database')
    @patch('main.RuleEngine')
    def test_skip_commit_on_dlq_failure(self, MockRuleEngine, MockDB, MockProducer, MockConsumer):
        # Setup
        mock_consumer = MockConsumer.return_value
        mock_producer = MockProducer.return_value

        # Simulate a message with missing tenant_id (triggers DLQ path)
        message = MagicMock()
        message.value = {"event_id": "e1", "payload": {}} # Missing tenant_id
        message.topic = "input_topic"
        message.partition = 0
        message.offset = 123

        # Create a mock for TopicPartition
        tp_mock = MagicMock()
        tp_mock.topic = "test_topic"
        tp_mock.partition = 0

        # Mock poll to return one batch with one message
        mock_consumer.poll.side_effect = [{tp_mock: [message]}, SystemExit("StopTest")]

        # Mock DLQ send to RAISE exception (simulate DLQ failure)
        mock_producer.send.side_effect = Exception("DLQ Down")

        try:
            main.main()
        except SystemExit:
            pass

        # Assertions
        # 1. DLQ send was attempted
        mock_producer.send.assert_called()
        args, _ = mock_producer.send.call_args
        self.assertEqual(args[0], main.DLQ_TOPIC)

        # 2. Commit should NOT be called because DLQ failed
        mock_consumer.commit.assert_not_called()

if __name__ == '__main__':
    unittest.main()
