from __future__ import annotations

from test.support_fake_deps import install
install()

import unittest

import script6


class AccountingParserTests(unittest.TestCase):
    def test_parse_csv_text_classifies_delivered_and_bounced_rows(self) -> None:
        csv_text = (
            'd,,2026-03-20 10:15:00,,Recipient One <one@gmail.com>,,success,2.0.0,queued as ok,mx1.gmail.com,,,,,,,1200,pool-a,,category-a\n'
            'b,,2026-03-20 11:45:00,,two@yahoo.com,,failed,5.7.1,message blocked because listed on blocklist,mx1.yahoo.com,,,,,,,980,pool-b,,category-b\n'
        )

        records = script6.parse_csv_text(csv_text, 'sample.csv')

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['result'], 'delivered')
        self.assertEqual(records[0]['recipient_domain'], 'gmail.com')
        self.assertEqual(records[0]['time_bucket'], '2026-03-20 10:00')
        self.assertEqual(records[1]['result'], 'bounced')
        self.assertEqual(records[1]['bounce_category'], 'blocklist')
        self.assertEqual(records[1]['recommended_action'], 'Fix IP/domain reputation before retry')

    def test_summarize_entity_builds_delivery_stats(self) -> None:
        records = [
            {'recipient_domain': 'gmail.com', 'result': 'delivered', 'bounce_category': 'unknown'},
            {'recipient_domain': 'gmail.com', 'result': 'bounced', 'bounce_category': 'spam-related'},
            {'recipient_domain': 'yahoo.com', 'result': 'delivered', 'bounce_category': 'unknown'},
        ]

        summary = script6.summarize_entity(records, 'recipient_domain', include_category=True)
        summary_by_domain = {row['value']: row for row in summary}

        self.assertEqual(summary_by_domain['gmail.com']['total'], 2)
        self.assertEqual(summary_by_domain['gmail.com']['delivery_rate'], 50.0)
        self.assertEqual(summary_by_domain['gmail.com']['top_bounce_category'], 'spam-related')
        self.assertEqual(summary_by_domain['yahoo.com']['delivered'], 1)
