from __future__ import annotations

import unittest

from tools import dns_shaker


class FakeDNSShaker(dns_shaker.DNSShaker):
    def query_record(self, domain: str, record_type: str) -> dict[str, object]:
        valid_records = {
            'NS': ['ns1.example.net'],
            'SOA': ['ns1.example.net hostmaster.example.net 1 7200 3600 1209600 3600'],
            'MX': ['10 mail.example.net'],
        }
        records = valid_records.get(record_type, [])
        return {
            'type': record_type,
            'valid': bool(records),
            'status': 'valid' if records else 'invalid',
            'records': records,
            'error': None if records else 'No answer returned',
            'command': f'dig +short {domain} {record_type}',
        }


class DNSShakerTests(unittest.TestCase):
    def test_normalize_domain_and_validation(self) -> None:
        self.assertEqual(dns_shaker.normalize_domain('https://Sub.Example.com/path'), 'sub.example.com')
        self.assertTrue(dns_shaker.is_domain_syntax_valid('sub.example.com'))
        self.assertFalse(dns_shaker.is_domain_syntax_valid('bad_domain'))

    def test_audit_domain_marks_partial_when_authority_is_present_but_apex_records_missing(self) -> None:
        checker = FakeDNSShaker()
        result = checker.audit_domain('Example.com')

        self.assertEqual(result['domain'], 'example.com')
        self.assertEqual(result['status'], 'valid')
        self.assertTrue(result['records']['NS']['valid'])
        self.assertFalse(result['records']['A']['valid'])
        self.assertIn('No A, AAAA, or CNAME record was found for the apex domain', result['summary']['notes'])
