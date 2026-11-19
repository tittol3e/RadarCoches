"""Contrato de ACK y recuperación sin declarar un broker simulado como real."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from actividad_ingesta.pipeline.distributed import consume, topic_for
from actividad_ingesta.pipeline.lab import Lab


class CheckpointTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.lab = Lab(self.root)
        self.lab.prepare_revision(0)
        with self.lab.store.db() as db:
            events = [json.loads(r[0]) for r in db.execute('SELECT payload FROM source_changes ORDER BY seq')]
        self.records = [SimpleNamespace(value=e, offset=n, topic='test', partition=0)
                        for n, e in enumerate(events)]
        self.consumer = MagicMock()
        self.consumer.__iter__.side_effect = lambda: iter(self.records)
        kafka = SimpleNamespace(KafkaConsumer=MagicMock(return_value=self.consumer))
        self.addCleanup(patch.stopall)
        patch('actividad_ingesta.pipeline.distributed.require_dependencies', return_value=(None, None, kafka)).start()
        patch.dict('sys.modules', {'kafka.structs': SimpleNamespace(
            OffsetAndMetadata=lambda offset, *args: offset,
            TopicPartition=lambda topic, partition: (topic, partition))}).start()

    def test_export_precedes_each_batched_commit(self):
        order = []
        self.consumer.commit.side_effect = lambda offsets: order.append(('commit', dict(offsets)))
        with patch('actividad_ingesta.pipeline.distributed.export_analytics',
                   side_effect=lambda root: order.append(('export', None)) or {}) as export:
            result = consume(self.root, export_every=4)
        self.assertEqual(result['consumed'], 10)
        self.assertEqual([x[0] for x in order], ['export', 'commit', 'export', 'commit', 'export', 'commit'])
        self.assertEqual([x[1][('test', 0)] for x in order if x[0] == 'commit'], [4, 8, 10])
        self.assertEqual(export.call_count, 3)
        self.consumer.close.assert_called_once_with(autocommit=False)

    def test_exact_batch_reuses_committed_projection(self):
        with patch('actividad_ingesta.pipeline.distributed.export_analytics',
                   side_effect=[{'unique_ads': 5}, {'unique_ads': 10}]) as export:
            result = consume(self.root, export_every=5)
        self.assertEqual(result['analytics'], {'unique_ads': 10})
        self.assertEqual(export.call_count, 2)

    def test_export_failure_does_not_ack_and_replay_is_idempotent(self):
        with patch('actividad_ingesta.pipeline.distributed.export_analytics', side_effect=OSError('disco')):
            with self.assertRaises(OSError):
                consume(self.root, export_every=4)
        self.consumer.commit.assert_not_called()
        self.assertEqual(self.lab.store.summary()['counts']['ads'], 4)
        with patch('actividad_ingesta.pipeline.distributed.export_analytics', return_value={}):
            consume(self.root, export_every=4)
        counts = self.lab.store.summary()['counts']
        self.assertEqual((counts['ads'], counts['history'], counts['consumed']), (10, 10, 10))

    def test_invalid_batch_is_rejected(self):
        with self.assertRaises(ValueError):
            consume(self.root, export_every=0)

    def test_runs_use_separate_topics_but_restarts_keep_topic(self):
        self.assertEqual(topic_for(self.root), topic_for(self.root / '.'))
        self.assertNotEqual(topic_for(self.root), topic_for(self.root / 'volumen'))
