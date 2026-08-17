from __future__ import annotations

import unittest

from spapi import Config, SpApiClient, classify_restrictions, endpoint_for_marketplaces


class RestrictionClassificationTests(unittest.TestCase):
    def test_empty_restrictions_are_sellable(self) -> None:
        self.assertEqual(classify_restrictions({"restrictions": []})["status"], "SELLABLE")

    def test_nonempty_without_reasons_is_restricted(self) -> None:
        result = classify_restrictions({"restrictions": [{"marketplaceId": "ATVPDKIKX0DER"}]})
        self.assertEqual(result["status"], "RESTRICTED")

    def test_approval_required(self) -> None:
        result = classify_restrictions({
            "restrictions": [{
                "reasons": [{
                    "reasonCode": "APPROVAL_REQUIRED",
                    "message": "Approval is required",
                    "links": [{"resource": "https://sellercentral.amazon.com/example"}],
                }]
            }]
        })
        self.assertEqual(result["status"], "APPROVAL_REQUIRED")
        self.assertTrue(result["approvalUrl"].startswith("https://"))
        self.assertNotIn("restrictions", result)

    def test_not_eligible_is_restricted(self) -> None:
        result = classify_restrictions({
            "restrictions": [{"reasons": [{"reasonCode": "NOT_ELIGIBLE"}]}]
        })
        self.assertEqual(result["status"], "RESTRICTED")

    def test_cross_region_marketplaces_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            endpoint_for_marketplaces(["ATVPDKIKX0DER", "A1F83G8C2ARO7P"])


class TransportSecurityTests(unittest.TestCase):
    def test_non_https_request_is_refused_before_network(self) -> None:
        client = SpApiClient(Config(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
            seller_id="seller",
            marketplace_id="ATVPDKIKX0DER",
        ))
        with self.assertRaisesRegex(ValueError, "non-TLS"):
            client._json_request("http://example.invalid/path")


if __name__ == "__main__":
    unittest.main()
