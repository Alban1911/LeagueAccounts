import threading
import time
import unittest

from leagueaccounts.account_manager import AccountManager
from leagueaccounts.models import Account


class SlowRankFetcher:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def fetch_rank(self, account):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)

        try:
            time.sleep(0.1)
            return {
                'tier': 'Gold',
                'division': 'II',
                'lp': '50',
                'level': '100',
                'reached_last_season': 'Platinum IV',
                'finished_last_season': 'Gold I',
            }
        finally:
            with self.lock:
                self.active -= 1


class AccountManagerRefreshTests(unittest.TestCase):
    def test_refresh_ranks_fetches_accounts_in_parallel(self):
        rank_fetcher = SlowRankFetcher()
        manager = AccountManager(root=None, rank_fetcher=rank_fetcher)
        manager.save_accounts = lambda: None
        manager.accounts = [
            Account(
                account_id=str(index),
                name=f'Player{index}#EUW',
                region='euw',
                region_display='EUW',
            )
            for index in range(4)
        ]

        manager.refresh_ranks()

        self.assertEqual(rank_fetcher.max_active, 4)
        self.assertTrue(all(account.tier == 'Gold' for account in manager.accounts))


if __name__ == '__main__':
    unittest.main()
