import html
import re
from urllib.parse import quote

import bs4
import requests
from bs4 import BeautifulSoup


class RankFetcher:
    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/125.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
    }

    APEX_TIERS = {'Challenger', 'Grandmaster', 'Master'}
    DIVISION_NUMERALS = {
        '1': 'I',
        '2': 'II',
        '3': 'III',
        '4': 'IV',
    }

    def fetch_rank(self, account):
        try:
            rank_info = self._fetch_from_opgg(account)
            if rank_info:
                return self._with_defaults(rank_info)
        except Exception:
            pass

        return {
            'tier': 'Error',
            'division': '',
            'lp': '',
            'level': '',
            'reached_last_season': '...',
            'finished_last_season': '...'
        }

    def _fetch_from_opgg(self, account):
        url = self._build_opgg_url(account.region, account.name)
        response = requests.get(url, headers=self.HEADERS, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        decoded_payload = html.unescape(response.text).replace('\\"', '"')
        if 'profile_icons/profileIcon' not in decoded_payload:
            raise ValueError('OP.GG profile payload was not found')

        rank_info = self._parse_current_rank_from_opgg(soup, decoded_payload)
        rank_info['level'] = self._parse_level_from_opgg(soup, decoded_payload)

        reached, finished = self._parse_last_season_from_opgg(decoded_payload)
        rank_info['reached_last_season'] = reached
        rank_info['finished_last_season'] = finished
        return rank_info

    def _build_opgg_url(self, region, summoner_name):
        game_name, tagline = self._split_riot_id(summoner_name)
        formatted_name = quote(game_name)
        if tagline:
            formatted_name = f'{formatted_name}-{quote(tagline)}'
        return f'https://op.gg/lol/summoners/{region}/{formatted_name}'

    def _split_riot_id(self, summoner_name):
        if '#' not in summoner_name:
            return summoner_name.strip(), ''

        game_name, tagline = summoner_name.rsplit('#', 1)
        return game_name.strip(), tagline.strip()

    def _parse_current_rank_from_opgg(self, soup, decoded_payload):
        tier = 'Unranked'
        division = ''
        lp = ''

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if isinstance(meta_desc, bs4.element.Tag) and meta_desc.has_attr('content'):
            parsed_rank = self._parse_rank_text(str(meta_desc['content']))
            if parsed_rank:
                tier, division, lp = parsed_rank

        if tier == 'Unranked':
            tier_info_matches = list(re.finditer(
                r'"tier_info":\{"lp":(?P<lp>\d+),"tier":"(?P<tier>[A-Z_]+)",'
                r'"label":"(?P<label>[^"]+)"\}',
                decoded_payload
            ))
            if tier_info_matches:
                latest = tier_info_matches[-1]
                tier, division, lp = self._normalize_rank(
                    latest.group('tier'),
                    self._division_from_label(latest.group('label')),
                    latest.group('lp')
                )

        return {
            'tier': tier,
            'division': division,
            'lp': lp,
        }

    def _parse_level_from_opgg(self, soup, decoded_payload):
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if isinstance(meta_desc, bs4.element.Tag) and meta_desc.has_attr('content'):
            level_match = re.search(r'\bLv\.\s*(\d+)\b', str(meta_desc['content']))
            if level_match:
                return level_match.group(1)

        profile_level_match = re.search(
            r'profile_icons/profileIcon\d+\.jpg.{0,1200}?<span[^>]*>(\d+)</span>',
            decoded_payload,
            re.DOTALL
        )
        if profile_level_match:
            return profile_level_match.group(1)

        react_level_match = re.search(
            r'profile_icons/profileIcon\d+\.jpg.{0,1600}?"children":(\d+)',
            decoded_payload,
            re.DOTALL
        )
        if react_level_match:
            return react_level_match.group(1)

        return ''

    def _parse_last_season_from_opgg(self, decoded_payload):
        history_pattern = re.compile(
            r'"season":"(?P<season>[^"]+)","rank_entries":\{'
            r'"high_rank_info":\{"tier":"(?P<high_tier>[^"]*)",'
            r'"lp":(?P<high_lp>null|"[^"]*").*?\},'
            r'"rank_info":\{"tier":"(?P<rank_tier>[^"]*)",'
            r'"lp":(?P<rank_lp>null|"[^"]*")',
            re.DOTALL
        )

        for match in history_pattern.finditer(decoded_payload):
            high_rank = self._format_history_rank(
                match.group('high_tier'),
                self._clean_lp_value(match.group('high_lp'))
            )
            finished_rank = self._format_history_rank(
                match.group('rank_tier'),
                self._clean_lp_value(match.group('rank_lp'))
            )

            if high_rank or finished_rank:
                return high_rank or finished_rank, finished_rank or high_rank

        return 'Unranked', 'Unranked'

    def _parse_rank_text(self, text):
        rank_match = re.search(
            r'\b(?P<tier>Challenger|Grandmaster|Master|Diamond|Emerald|Platinum|Gold|Silver|Bronze|Iron)'
            r'\s*(?P<division>IV|III|II|I|[1-4])?\s+(?P<lp>[\d,]+)\s*LP\b',
            text,
            re.IGNORECASE
        )
        if not rank_match:
            return None

        return self._normalize_rank(
            rank_match.group('tier'),
            rank_match.group('division') or '',
            rank_match.group('lp')
        )

    def _normalize_rank(self, tier, division='', lp=''):
        normalized_tier = str(tier).replace('_', ' ').title().replace(' ', '')
        if normalized_tier.lower() == 'grandmaster':
            normalized_tier = 'Grandmaster'

        normalized_division = str(division or '').strip().upper()
        normalized_division = self.DIVISION_NUMERALS.get(normalized_division, normalized_division)
        if normalized_tier in self.APEX_TIERS:
            normalized_division = ''

        normalized_lp = str(lp or '').replace(',', '').strip()
        return normalized_tier, normalized_division, normalized_lp

    def _division_from_label(self, label):
        label_match = re.search(r'\b(?:[A-Z]+)\s+([1-4])\b', label or '')
        return label_match.group(1) if label_match else ''

    def _format_history_rank(self, tier_text, lp):
        tier_text = str(tier_text or '').strip()
        if not tier_text:
            return ''

        text_match = re.match(
            r'(?P<tier>Challenger|Grandmaster|Master|Diamond|Emerald|Platinum|Gold|Silver|Bronze|Iron)'
            r'\s*(?P<division>IV|III|II|I|[1-4])?',
            tier_text,
            re.IGNORECASE
        )
        if not text_match:
            return tier_text.title()

        tier, division, _ = self._normalize_rank(
            text_match.group('tier'),
            text_match.group('division') or '',
            lp or ''
        )
        rank_parts = [tier]
        if division:
            rank_parts.append(division)
        if lp:
            rank_parts.append(f'{lp}LP')
        return ' '.join(rank_parts)

    def _clean_lp_value(self, value):
        value = str(value or '').strip()
        if value == 'null' or not value:
            return ''
        return value.strip('"').replace(',', '')

    def _with_defaults(self, rank_info):
        return {
            'tier': rank_info.get('tier') or 'Unranked',
            'division': rank_info.get('division') or '',
            'lp': rank_info.get('lp') or '',
            'level': rank_info.get('level') or '',
            'reached_last_season': rank_info.get('reached_last_season') or 'Unranked',
            'finished_last_season': rank_info.get('finished_last_season') or 'Unranked'
        }
