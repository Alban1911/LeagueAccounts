import unittest

from bs4 import BeautifulSoup

from leagueaccounts.rank_fetcher import RankFetcher


class RankFetcherParserTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = RankFetcher()

    def test_opgg_current_rank_and_level(self):
        html_doc = """
        <html>
          <head>
            <meta name="description" content="Hide on bush#KR1 / Challenger 1 1952LP / 248Win 186Lose Win rate 57%"/>
          </head>
          <body>
            <img src="https://opgg-static.akamaized.net/meta/images/profile_icons/profileIcon6.jpg"/>
            <div><span>909</span></div>
          </body>
        </html>
        """
        soup = BeautifulSoup(html_doc, 'html.parser')

        rank = self.fetcher._parse_current_rank_from_opgg(soup, html_doc)
        level = self.fetcher._parse_level_from_opgg(soup, html_doc)

        self.assertEqual(rank, {'tier': 'Challenger', 'division': '', 'lp': '1952'})
        self.assertEqual(level, '909')

    def test_opgg_unranked_level_from_meta_description(self):
        html_doc = """
        <html>
          <head>
            <meta name="description" content="Faker#T 1 / Lv. 71"/>
          </head>
        </html>
        """
        soup = BeautifulSoup(html_doc, 'html.parser')

        rank = self.fetcher._parse_current_rank_from_opgg(soup, html_doc)
        level = self.fetcher._parse_level_from_opgg(soup, html_doc)

        self.assertEqual(rank, {'tier': 'Unranked', 'division': '', 'lp': ''})
        self.assertEqual(level, '71')

    def test_opgg_last_season_high_and_finished_ranks(self):
        payload = (
            '"season":"S2025 ","rank_entries":{'
            '"high_rank_info":{"tier":"challenger","lp":"1,255","tier_image_url":"","tier_mini_image_url":""},'
            '"rank_info":{"tier":"master","lp":"285","tier_image_url":"","tier_mini_image_url":""}}'
        )

        reached, finished = self.fetcher._parse_last_season_from_opgg(payload)

        self.assertEqual(reached, 'Challenger 1255LP')
        self.assertEqual(finished, 'Master 285LP')


if __name__ == '__main__':
    unittest.main()
