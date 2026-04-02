from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libspace_cli.crypto import build_daily_aes_key, decrypt_payload, encrypt_payload


class CryptoTests(unittest.TestCase):
    def test_build_daily_aes_key_matches_frontend_rule(self) -> None:
        date = datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(build_daily_aes_key(date, "Asia/Shanghai"), "2026040110406202")

    def test_encrypt_payload_round_trip(self) -> None:
        date = datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        payload = {"seat_id": 123, "segment": 456}
        encrypted = encrypt_payload(payload, date, "Asia/Shanghai")
        decrypted = decrypt_payload(encrypted, date, "Asia/Shanghai")
        self.assertEqual(decrypted, '{"seat_id":123,"segment":456}')


if __name__ == "__main__":
    unittest.main()
