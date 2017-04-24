# -*- coding: utf-8 -*-
from os.path import basename, splitext
from io import BytesIO
from logging import getLogger
from zipfile import ZipFile

from babelfish import Language, language_converters
from requests import Session
from guessit import guessit

from . import ParserBeautifulSoup, Provider
from .. import __short_version__
from ..subtitle import Subtitle, fix_line_ending
from ..video import Video, Episode
from ..converters.subscene import supported_languages

logger = getLogger(__name__)

language_converters.register('subscene = subliminal.converters.subscene:SubsceneConverter')

language_ids = {
        'ara':  2, 'dan': 10, 'nld': 11, 'eng': 13, 'fas': 46, 'fin': 17,
        'fra': 18, 'heb': 22, 'ind': 44, 'ita': 26, 'msa': 50, 'nor': 30,
        'ron': 33, 'spa': 38, 'swe': 39, 'vie': 45, 'sqi':  1, 'hye': 73,
        'aze': 55, 'eus': 74, 'bel': 68, 'ben': 54, 'bos': 60, 'bul':  5,
        'mya': 61, 'cat': 49, 'hrv':  8, 'ces':  9, 'epo': 47, 'est': 16,
        'kat': 62, 'deu': 19, 'ell': 21, 'kal': 57, 'hin': 51, 'hun': 23,
        'isl': 25, 'jpn': 27, 'kor': 28, 'kur': 52, 'lav': 29, 'lit': 43,
        'mkd': 48, 'mal': 64, 'mni': 65, 'mon': 72, 'pus': 67, 'pol': 31,
        'por': 32, 'pan': 66, 'rus': 34, 'srp': 35, 'sin': 58, 'slk': 36,
        'slv': 37, 'som': 70, 'tgl': 53, 'tam': 59, 'tel': 63, 'tha': 40,
        'tur': 41, 'ukr': 56, 'urd': 42, 'yor': 71
}


def get_video_filename(video):
    return splitext(basename(video.name))[0]


class SubsceneSubtitle(Subtitle):
    """Subscene Subtitle."""
    provider_name = 'subscene'

    def __init__(self, language, hearing_impaired, page_link, name, year=None):
        super(SubsceneSubtitle, self).__init__(language, hearing_impaired, page_link)
        self.name = name

        self._info = guessit(self.name)

        if year:
            self._info["year"] = year

        self.video = Video.fromname(name)

    @property
    def id(self):
        i = self.page_link.rindex('/') + 1
        return int(self.page_link[i:])

    @property
    def title(self):
        return self._info["title"]

    def get_matches(self, video):
        matches = self._matches_for(video, 'title', 'year', 'format', 'release_group', 'video_codec', 'audio_codec')

        if isinstance(video, Episode):
            matches.update(self._matches_for(video, 'series', 'season', 'episode', 'hearing_impaired'))

        if get_video_filename(video) == self.name:
            matches.add("name")

        return matches

    def _matches_for(self, video, *attrs):
        matches = set()
        for a in attrs:
            if a not in self._info:
                continue

            v = getattr(video, a)
            if v and v == self._info[a]:
                matches.add(a)
        return matches


class SubsceneProvider(Provider):
    """Subscene Provider."""

    server_url = 'https://subscene.com'
    languages = supported_languages

    def initialize(self):
        logger.info("Creating session")
        self.session = Session()
        self.session.headers['User-Agent'] = 'Subliminal/%s' % __short_version__

    def terminate(self):
        logger.info("Closing session")
        self.session.close()

    def query(self, video):
        q = get_video_filename(video)
        subtitles = self._simple_query(q)

        if not subtitles:
            subtitles = self._extended_query(video)

        logger.info("Totally %s subtitles found" % len(subtitles))
        return subtitles

    def list_subtitles(self, video, languages):
        self._create_filters(languages)
        self._enable_filters()
        return [s for s in self.query(video) if s.language in languages]

    def download_subtitle(self, subtitle):
        logger.info("Downloading subtitle %r", str(subtitle.id))
        soup = self._get_soup(subtitle.page_link)
        url = soup.find("div", "download").a.get("href")
        r = self.session.get(self.server_url + url)
        logger.info("Extracting downloaded subtitle")
        with ZipFile(BytesIO(r.content)) as zf:
            fn = [n for n in zf.namelist() if n.endswith('.srt')][0]
            content = zf.read(fn)
        subtitle.content = fix_line_ending(content)

    def _simple_query(self, q):
        subtitles = []

        logger.info('Searching for "%s"' % q)
        soup = self._get_soup('/subtitles/title', q=q)

        if 'Subtitle search by' in str(soup):
            subtitles = self._subtitles_from_soup(soup)

        if not subtitles:
            search_result = soup.find("div", "search-results")
            if search_result is not None:
                for a in search_result.ul.find_all("a"):
                    logger.info("Extracting subtitles for '%s'" % a.text)
                    soup = self._get_soup(a.get("href"))
                    subtitles.extend(self._subtitles_from_soup(soup))

        return subtitles

    def _extended_query(self, video):
        # find a subtitle only with correct name, and then from it's page find correct video page
        logger.info("Using extended search algorithm")

        self._disable_filters()

        video_title = video.title.lower()
        subtitles = self._simple_query(video_title)

        video_page = None
        for subtitle in subtitles:
            if subtitle.title.lower() == video_title:
                try:
                    video_page = self._get_soup(subtitle.page_link).find("div", "bread").a.get("href")
                    break
                except AttributeError:
                    continue

        if video_page is None:
            return []

        self._enable_filters()
        return self._subtitles_from_soup(self._get_soup(video_page))

    def _get_soup(self, url, **params):
        kwargs = {"url": (self.server_url + url)}

        if params:
            kwargs["params"] = params

        logger.debug("Opening url '%s' with params '%s'" % (kwargs["url"], params))
        r = self.session.get(**kwargs)
        r.raise_for_status()
        return ParserBeautifulSoup(r.content, ['html.parser'])

    def _subtitles_from_soup(self, soup):
        subtitles = []
        kwargs = {}

        try:
            kwargs["year"] = int(soup.find("div", "header").strong.parent.text.strip()[5:].strip())
        except AttributeError:
            pass

        for tr in soup.table.tbody.find_all("tr"):
            try:
                kwargs["language"] = Language.fromsubscene(tr.span.text.strip())
            except NotImplementedError:
                continue

            kwargs["page_link"] = tr.a.get("href")
            kwargs["name"] = tr.span.find_next("span").text.strip()
            kwargs["hearing_impaired"] = bool(tr.find("td", "a41"))
            subtitles.append(SubsceneSubtitle(**kwargs))

        logger.debug("%s subtitles found" % len(subtitles))
        return subtitles

    def _create_filters(self, languages):
        self.filters = dict(ForeignOnly="False", HearingImpaired="2")

        self.filters["LanguageFilter"] = ",".join((str(language_ids[l.alpha3]) for l in languages))

        logger.info("Filter created: '%s'" % self.filters)

    def _enable_filters(self):
        self.session.cookies.update(self.filters)
        logger.info("Filters applied")

    def _disable_filters(self):
        for key in self.filters:
            self.session.cookies.pop(key)
        logger.info("Filters discarded")
