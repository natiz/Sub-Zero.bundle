# coding=utf-8

import logging
import traceback

from num2words import num2words
from subliminal.providers.subscene import SubsceneProvider as _SubsceneProvider, SubsceneSubtitle as _SubsceneSubtitle, \
    guessit, Video, Language, Episode, get_video_filename

logger = logging.getLogger(__name__)


class InsufficientGuessData(Exception):
    pass


class SubsceneSubtitle(_SubsceneSubtitle):
    is_pack = False
    video_filename = None

    def __init__(self, language, hearing_impaired, page_link, name, year=None, imdb_id=None, is_series=False,
                 is_pack=False, video_filename=None,
                 force_episode=None):
        super(_SubsceneSubtitle, self).__init__(language, hearing_impaired, page_link)
        self.name = name
        self.is_pack = is_pack

        self._info = dict(guessit(self.name))

        if year:
            self._info["year"] = year

        if is_pack and not self._info.get("episode", None) and force_episode:
            # fill episode
            self._info["episode"] = force_episode

        self._info["resolution"] = self._info.get("screen_size")

        if is_series:
            self._info["series"] = self._info["title"]
            self._info["title"] = self._info.get("episode_title", None)
            if imdb_id:
                self._info["series_imdb_id"] = imdb_id
        else:
            if imdb_id:
                self._info["imdb_id"] = imdb_id

        self.release_info = name

    def get_matches(self, video):
        matches = self._matches_for(video, 'title', 'year', 'format', 'release_group', 'video_codec', 'audio_codec',
                                    'imdb_id', 'resolution')

        if isinstance(video, Episode):
            matches.update(self._matches_for(video, 'series', 'season', 'episode', 'hearing_impaired',
                                             'series_imdb_id', 'title'))

        if get_video_filename(video) == self.name:
            matches.add("hash")

        return matches


class SubsceneProvider(_SubsceneProvider):
    subtitle_class = SubsceneSubtitle

    def list_subtitles(self, video, languages):
        self._create_filters(languages)
        self._enable_filters()
        return [s for s in self.query(video, languages) if s.language in languages]

    def _simple_query(self, q, languages, video=None):
        subtitles = []

        logger.info('Searching for "%s"' % q)
        soup = self._get_soup('/subtitles/title', q=q)

        # release name search result
        if 'Subtitle search by' in str(soup):
            subtitles = self._subtitles_from_soup(soup, languages, video=video)

        # full text/title search result
        if not subtitles:
            verify_result_by = None

            if isinstance(video, Episode):
                # only scrape the page with the correct season
                verify_result_by = num2words(video.season, ordinal=True)

            search_result = soup.find("div", "search-result")
            if search_result is not None:
                for a in search_result.ul.find_all("a"):
                    if verify_result_by and verify_result_by not in a.text.lower():
                        continue

                    logger.info("Extracting subtitles for '%s'" % a.text)
                    soup = self._get_soup(a.get("href"))
                    subtitles.extend(self._subtitles_from_soup(soup, languages, video=video))

        return subtitles

    def _extended_query(self, video, languages):
        # find a subtitle only with correct name, and then from it's page find correct video page
        logger.info("Using extended search algorithm")

        self._disable_filters()

        if isinstance(video, Episode):
            video_title = video.series.lower()
        else:
            video_title = video.title.lower()

        subtitles = self._simple_query(video_title, languages, video=video)
        return subtitles

        # video_page = None
        # for subtitle in subtitles:
        #     if video_title in subtitle.title.lower():
        #         try:
        #             video_page = self._get_soup(subtitle.page_link).find("div", "bread").a.get("href")
        #             break
        #         except AttributeError:
        #             continue
        #
        # if video_page is None:
        #     return []
        #
        # self._enable_filters()
        # return self._subtitles_from_soup(self._get_soup(video_page), video=video)

    def query(self, video, languages):
        q = get_video_filename(video)
        subtitles = self._simple_query(q, languages, video=video)

        # if not subtitles:
        #    subtitles = self._extended_query(video, languages)
        # subtitles = self._extended_query(video, languages)

        logger.info("Totally %s subtitles found" % len(subtitles))
        return subtitles

    def _subtitles_from_soup(self, soup, languages, video=None):
        subtitles = []
        kwargs = {}

        try:
            kwargs["year"] = int(soup.find("div", "header").strong.parent.text.strip()[5:].strip())
        except AttributeError:
            pass

        first_sub = True
        imdb_id = None
        for tr in soup.table.tbody.find_all("tr"):
            try:
                language = tr.span.text.strip()
            except AttributeError:
                continue

            try:
                kwargs["language"] = Language.fromsubscene(language)
            except NotImplementedError:
                continue

            # check language before even considering this subtitle
            if kwargs["language"] not in languages:
                continue

            kwargs["page_link"] = tr.a.get("href")
            kwargs["name"] = tr.span.find_next("span").text.strip()
            kwargs["hearing_impaired"] = bool(tr.find("td", "a41"))

            if first_sub:
                # try finding imdb_id

                try:
                    imdb_id = self._get_soup(kwargs["page_link"]).find("div", "header").find("a", "imdb").get("href") \
                        .split("/")[-1]
                except:
                    pass
                first_sub = False

            kwargs["imdb_id"] = imdb_id
            kwargs["video_filename"] = get_video_filename(video)

            # guess info based on name, to filter out season packs
            if isinstance(video, Episode):
                info = guessit(kwargs["name"])
                season = info.get("season", None)
                episode = info.get("episode", None)
                kwargs["is_series"] = True
                if season != video.season:
                    # skip invalid season
                    continue

                if episode is None:
                    # check pack
                    kwargs["is_pack"] = True
                    kwargs["force_episode"] = video.episode
                    logger.debug("Accepting subtitle %s because it appears to be a pack" % kwargs["name"])

                elif episode and episode != video.episode:
                    # skip invalid episode
                    continue

            try:
                subtitles.append(self.subtitle_class(**kwargs))
            except InsufficientGuessData:
                # insufficient data for guessit
                logger.debug("Skipping %s because parsing failed: %s" % (kwargs["name"], traceback.format_exc()))
                continue

        logger.debug("%s subtitles found" % len(subtitles))
        return subtitles
