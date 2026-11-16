"""Regresiones del arranque Windows: puertos vacíos y disponibilidad HTTP."""
import socket
import unittest
from unittest.mock import patch

import httpx

from scripts.run_distributed import check_api_ports, wait_for_apis


class DistributedStartupTest(unittest.TestCase):
    def test_empty_port_check_does_not_make_http_request(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        with patch('httpx.Client', side_effect=AssertionError('No HTTP before startup')):
            check_api_ports((port,))

    def test_occupied_port_is_rejected_and_service_is_preserved(self):
        with socket.socket() as service:
            service.bind(('127.0.0.1', 0))
            service.listen()
            port = service.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, f'127.0.0.1:{port}'):
                check_api_ports((port,))
            self.assertEqual(service.getsockname()[1], port)

    def test_starting_api_retries_connect_timeout_then_checks_identity(self):
        calls = []

        def handle(request):
            calls.append(str(request.url))
            if len(calls) == 1:
                raise httpx.ConnectTimeout('starting', request=request)
            return httpx.Response(200, json=dict(source='demo_a', synthetic=True))

        client = httpx.Client(transport=httpx.MockTransport(handle))
        with patch('httpx.Client', return_value=client), patch('scripts.run_distributed.time.sleep'):
            wait_for_apis({'demo_a': 'http://127.0.0.1:8771'}, [], timeout=2)
        self.assertEqual(calls, ['http://127.0.0.1:8771/health'] * 2)

    def test_wrong_service_is_not_accepted(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=dict(source='other', synthetic=True))))
        with patch('httpx.Client', return_value=client):
            with self.assertRaisesRegex(RuntimeError, 'no es la API DEMO'):
                wait_for_apis({'demo_a': 'http://127.0.0.1:8771'}, [])
