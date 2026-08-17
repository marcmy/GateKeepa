from __future__ import annotations

import io
import json
import struct
import unittest
from unittest import mock

import native_host


class NativeMessageProtocolTests(unittest.TestCase):
    def test_write_and_read_round_trip(self) -> None:
        stream = io.BytesIO()
        native_host.write_message(stream, {"id": "abc", "request": {"type": "ping"}})
        stream.seek(0)
        payload = native_host.read_message(stream)
        self.assertEqual(payload, {"id": "abc", "request": {"type": "ping"}})

    def test_oversized_message_is_rejected(self) -> None:
        stream = io.BytesIO(struct.pack("<I", native_host.MAX_MESSAGE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "size"):
            native_host.read_message(stream)

    def test_non_object_message_is_rejected(self) -> None:
        raw = json.dumps([1, 2, 3]).encode("utf-8")
        stream = io.BytesIO(struct.pack("<I", len(raw)) + raw)
        with self.assertRaisesRegex(ValueError, "JSON object"):
            native_host.read_message(stream)


class NativeHostValidationTests(unittest.TestCase):
    def test_wrong_extension_id_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            native_host.verify_firefox_invoker(["host.exe", "manifest.json", "evil@example.com"])

    def test_expected_extension_id_is_accepted(self) -> None:
        native_host.verify_firefox_invoker([
            "host.exe", "manifest.json", native_host.ALLOWED_EXTENSION_ID
        ])

    @mock.patch.object(native_host, "load_settings")
    def test_invalid_asin_is_rejected(self, load_settings: mock.Mock) -> None:
        load_settings.return_value = {"marketplace_id": "ATVPDKIKX0DER"}
        with self.assertRaisesRegex(ValueError, "Invalid ASIN"):
            native_host.validate_eligibility_request({"asins": ["not-an-asin"]})

    @mock.patch.object(native_host, "get_secret")
    @mock.patch.object(native_host, "load_settings")
    def test_ping_reports_native_transport(self, load_settings: mock.Mock, get_secret: mock.Mock) -> None:
        load_settings.return_value = {
            "client_id": "client",
            "seller_id": "ABCDEFGHIJ",
            "marketplace_id": "ATVPDKIKX0DER",
        }
        get_secret.return_value = "present"
        response = native_host.handle_request({"type": "ping"})
        self.assertTrue(response["ok"])
        self.assertTrue(response["configured"])
        self.assertEqual(response["transport"], "native-messaging")
        self.assertEqual(response["service"], "GateKeepaNativeHost")

    @mock.patch.object(native_host, "get_client")
    @mock.patch.object(native_host, "load_settings")
    def test_eligibility_uses_client_without_network_listener(
        self, load_settings: mock.Mock, get_client: mock.Mock
    ) -> None:
        load_settings.return_value = {"marketplace_id": "ATVPDKIKX0DER"}
        fake_client = mock.Mock()
        fake_client.get_restrictions.return_value = {
            "status": "SELLABLE", "reasonCodes": [], "message": "", "approvalUrl": None
        }
        get_client.return_value = fake_client
        response = native_host.handle_request({
            "type": "eligibility",
            "asins": ["B012345678"],
            "marketplaceIds": ["ATVPDKIKX0DER"],
            "conditionType": "used_good",
        })
        self.assertTrue(response["ok"])
        self.assertEqual(response["results"]["B012345678"]["status"], "SELLABLE")
        fake_client.get_restrictions.assert_called_once()


if __name__ == "__main__":
    unittest.main()
