import unittest

from balatro_agent.client import BalatroBotClient, BalatroBotError


class BalatroBotClientTests(unittest.TestCase):
    def test_call_sends_json_rpc_payload_and_returns_result(self):
        captured = []

        def transport(payload, base_url, timeout):
            captured.append((payload, base_url, timeout))
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {"state": "SHOP"}}

        client = BalatroBotClient(
            base_url="http://127.0.0.1:12346",
            timeout=2.5,
            transport=transport,
        )

        result = client.call("gamestate")

        self.assertEqual(result, {"state": "SHOP"})
        self.assertEqual(captured[0][1], "http://127.0.0.1:12346")
        self.assertEqual(captured[0][2], 2.5)
        self.assertEqual(
            captured[0][0],
            {"jsonrpc": "2.0", "method": "gamestate", "params": {}, "id": 1},
        )

    def test_call_raises_balatrobot_error_with_name(self):
        def transport(payload, base_url, timeout):
            return {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "error": {
                    "code": -32002,
                    "message": "Wrong phase",
                    "data": {"name": "INVALID_STATE"},
                },
            }

        client = BalatroBotClient(transport=transport)

        with self.assertRaises(BalatroBotError) as raised:
            client.call("play", {"cards": [0]})

        self.assertEqual(raised.exception.code, -32002)
        self.assertEqual(raised.exception.name, "INVALID_STATE")
        self.assertIn("Wrong phase", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
