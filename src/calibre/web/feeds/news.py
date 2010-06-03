from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Defines various abstract base classes that can be subclassed to create powerful news fetching recipes.
'''
__docformat__ = "restructuredtext en"


import os, time, traceback, re, urlparse, sys
from collections import defaultdict
from functools import partial
from contextlib import nested, closing


from calibre import browser, __appname__, iswindows, \
                    strftime, preferred_encoding
from calibre.ebooks.BeautifulSoup import BeautifulSoup, NavigableString, CData, Tag
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre import entity_to_unicode
from calibre.web import Recipe
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.metadata import MetaInformation
from calibre.web.feeds import feed_from_xml, templates, feeds_from_index, Feed
from calibre.web.fetch.simple import option_parser as web2disk_option_parser
from calibre.web.fetch.simple import RecursiveFetcher
from calibre.utils.threadpool import WorkRequest, ThreadPool, NoResultsPending
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import now as nowf

class LoginFailed(ValueError):
    pass

class DownloadDenied(ValueError):
    pass

class BasicNewsRecipe(Recipe):
    '''
    Abstract base class that contains logic needed in all feed fetchers.
    '''

    #: The title to use for the ebook
    title                  = _('Unknown News Source')

    #: A couple of lines that describe the content this recipe downloads.
    #: This will be used primarily in a GUI that presents a list of recipes.
    description = ''

    #: The author of this recipe
    __author__             = __appname__

    #: Minimum calibre version needed to use this recipe
    requires_version = (0, 6, 0)

    #: The language that the news is in. Must be an ISO-639 code either
    #: two or three characters long
    language               = 'und'

    #: Maximum number of articles to download from each feed. This is primarily
    #: useful for feeds that don't have article dates. For most feeds, you should
    #: use :attr:`BasicNewsRecipe.oldest_article`
    max_articles_per_feed  = 100

    #: Oldest article to download from this news source. In days.
    oldest_article         = 7.0

    #: Number of levels of links to follow on article webpages
    recursions             = 0

    #: Delay between consecutive downloads in seconds
    delay                  = 0

    #: Publication type
    #: Set to newspaper, magazine or blog
    publication_type = 'unknown'

    #: Number of simultaneous downloads. Set to 1 if the server is picky.
    #: Automatically reduced to 1 if :attr:`BasicNewsRecipe.delay` > 0
    simultaneous_downloads = 5

    #: If False the remote server is contacted by only one thread at a time
    multithreaded_fetch = False

    #: Timeout for fetching files from server in seconds
    timeout                = 120.0

    #: The format string for the date shown on the first page.
    #: By default: Day_Name, Day_Number Month_Name Year
    timefmt                = ' [%a, %d %b %Y]'

    #: List of feeds to download
    #: Can be either ``[url1, url2, ...]`` or ``[('title1', url1), ('title2', url2),...]``
    feeds = None

    #: Max number of characters in the short description
    summary_length         = 500

    #: Convenient flag to disable loading of stylesheets for websites
    #: that have overly complex stylesheets unsuitable for conversion
    #: to ebooks formats
    #: If True stylesheets are not downloaded and processed
    no_stylesheets         = False

    #: Convenient flag to strip all javascript tags from the downloaded HTML
    remove_javascript      = True

    #: If True the GUI will ask the user for a username and password
    #: to use while downloading
    #: @type: boolean
    needs_subscription     = False

    #: If True the navigation bar is center aligned, otherwise it is left aligned
    center_navbar = True

    #: Specify an override encoding for sites that have an incorrect
    #: charset specification. The most common being specifying ``latin1`` and
    #: using ``cp1252``. If None, try to detect the encoding. If it is a
    #: callable, the callable is called with two arguments: The recipe object
    #: and the source to be decoded. It must return the decoded source.
    encoding               = None

    #: Normally we try to guess if a feed has full articles embedded in it
    #: based on the length of the embedded content. If `None`, then the
    #: default guessing is used. If `True` then the we always assume the feeds has
    #: embedded content and if `False` we always assume the feed does not have
    #: embedded content.
    use_embedded_content   = None

    #: Set to True and implement :method:`get_obfuscated_article` to handle
    #: websites that try to make it difficult to scrape content.
    articles_are_obfuscated = False

    #: Reverse the order of articles in each feed
    reverse_article_order = False

    #: Specify any extra :term:`CSS` that should be addded to downloaded :term:`HTML` files
    #: It will be inserted into `<style>` tags, just before the closing
    #: `</head>` tag thereby overriding all :term:`CSS` except that which is
    #: declared using the style attribute on individual :term:`HTML` tags.
    #: For example::
    #:
    #:     extra_css = '.heading { font: serif x-large }'
    #:
    extra_css              = None

    #: If True empty feeds are removed from the output.
    #: This option has no effect if parse_index is overriden in
    #: the sub class. It is meant only for recipes that return a list
    #: of feeds using `feeds` or :method:`get_feeds`.
    remove_empty_feeds = False

    #: List of regular expressions that determines which links to follow
    #: If empty, it is ignored. Used only if is_link_wanted is
    #: not implemented. For example::
    #:
    #:     match_regexps = [r'page=[0-9]+']
    #:
    #: will match all URLs that have `page=some number` in them.
    #:
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    match_regexps         = []

    #: List of regular expressions that determines which links to ignore
    #: If empty it is ignored. Used only if is_link_wanted is not
    #: implemented. For example::
    #:
    #:     filter_regexps = [r'ads\.doubleclick\.net']
    #:
    #: will remove all URLs that have `ads.doubleclick.net` in them.
    #:
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    filter_regexps        = []

    #: Recipe specific options to control the conversion of the downloaded
    #: content into an e-book. These will override any user or plugin specified
    #: values, so only use if absolutely necessary. For example::
    #:
    #:   conversion_options = {
    #:     'base_font_size'   : 16,
    #:     'tags'             : 'mytag1,mytag2',
    #:     'title'            : 'My Title',
    #:     'linearize_tables' : True,
    #:   }
    #:
    conversion_options = {}

    #: List of tags to be removed. Specified tags are removed from downloaded HTML.
    #: A tag is specified as a dictionary of the form::
    #:
    #:    {
    #:     name      : 'tag name',   #e.g. 'div'
    #:     attrs     : a dictionary, #e.g. {class: 'advertisment'}
    #:    }
    #:
    #: All keys are optional. For a full explanantion of the search criteria, see
    #: `Beautiful Soup <http://www.crummy.com/software/BeautifulSoup/documentation.html#The basic find method: findAll(name, attrs, recursive, text, limit, **kwargs)>`_
    #: A common example::
    #:
    #:   remove_tags = [dict(name='div', attrs={'class':'advert'})]
    #:
    #: This will remove all `<div class="advert">` tags and all
    #: their children from the downloaded :term:`HTML`.
    remove_tags           = []

    #: Remove all tags that occur after the specified tag.
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: For example::
    #:
    #:     remove_tags_after = [dict(id='content')]
    #:
    #: will remove all
    #: tags after the first element with `id="content"`.
    remove_tags_after     = None

    #: Remove all tags that occur before the specified tag.
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: For example::
    #:
    #:     remove_tags_before = dict(id='content')
    #:
    #: will remove all
    #: tags before the first element with `id="content"`.
    remove_tags_before    = None

    #: List of attributes to remove from all tags
    #: For example::
    #:
    #:   remove_attributes = ['style', 'font']
    remove_attributes = []

    #: Keep only the specified tags and their children.
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: If this list is not empty, then the `<body>` tag will be emptied and re-filled with
    #: the tags that match the entries in this list. For example::
    #:
    #:     keep_only_tags = [dict(id=['content', 'heading'])]
    #:
    #: will keep only tags that have an `id` attribute of `"content"` or `"heading"`.
    keep_only_tags        = []

    #: List of :term:`regexp` substitution rules to run on the downloaded :term:`HTML`.
    #: Each element of the
    #: list should be a two element tuple. The first element of the tuple should
    #: be a compiled regular expression and the second a callable that takes
    #: a single match object and returns a string to replace the match. For example::
    #:
    #:     preprocess_regexps = [
    #:        (re.compile(r'<!--Article ends here-->.*</body>', re.DOTALL|re.IGNORECASE),
    #:         lambda match: '</body>'),
    #:     ]
    #:
    #: will remove everythong from `<!--Article ends here-->` to `</body>`.
    preprocess_regexps    = []

    #: The CSS that is used to style the templates, i.e., the navigation bars and
    #: the Tables of Contents. Rather than overriding this variable, you should
    #: use `extra_css` in your recipe to customize look and feel.
    template_css = u'''
            .article_date {
                color: gray; font-family: monospace;
            }

            .article_description {
                font-family: sans; text-indent: 0pt;
            }

            a.article {
                font-weight: bold;
            }

            a.feed {
                font-weight: bold;
            }

            .calibre_navbar {
                font-family:monospace;
            }
    '''

    #: By default, calibre will use a default image for the masthead (Kindle only).
    #: Override this in your recipe to provide a url to use as a masthead.
    masthead_url = None

    #: Set to a non empty string to disable this recipe
    #: The string will be used as the disabled message
    recipe_disabled = None


    # See the built-in profiles for examples of these settings.

    def short_title(self):
        return self.title

    def is_link_wanted(self, url, tag):
        '''
        Return True if the link should be followed or False otherwise. By
        default, raises NotImplementedError which causes the downloader to
        ignore it.

        :param url: The URL to be followed
        :param tag: The Tag from which the URL was derived
        '''
        raise NotImplementedError

    def get_cover_url(self):
        '''
        Return a :term:`URL` to the cover image for this issue or `None`.
        By default it returns the value of the member `self.cover_url` which
        is normally `None`. If you want your recipe to download a cover for the e-book
        override this method in your subclass, or set the member variable `self.cover_url`
        before this method is called.
        '''
        return getattr(self, 'cover_url', None)

    def get_masthead_url(self):
        '''
        Return a :term:`URL` to the masthead image for this issue or `None`.
        By default it returns the value of the member `self.masthead_url` which
        is normally `None`. If you want your recipe to download a masthead for the e-book
        override this method in your subclass, or set the member variable `self.masthead_url`
        before this method is called.
        Masthead images are used in Kindle MOBI files.
        '''
        return getattr(self, 'masthead_url', None)

    def get_feeds(self):
        '''
        Return a list of :term:`RSS` feeds to fetch for this profile. Each element of the list
        must be a 2-element tuple of the form (title, url). If title is None or an
        empty string, the title from the feed is used. This method is useful if your recipe
        needs to do some processing to figure out the list of feeds to download. If
        so, override in your subclass.
        '''
        if not self.feeds:
            raise NotImplementedError
        if self.test:
            return self.feeds[:2]
        return self.feeds

    @classmethod
    def print_version(self, url):
        '''
        Take a `url` pointing to the webpage with article content and return the
        :term:`URL` pointing to the print version of the article. By default does
        nothing. For example::

            def print_version(self, url):
                return url + '?&pagewanted=print'

        '''
        raise NotImplementedError

    @classmethod
    def image_url_processor(cls, baseurl, url):
        '''
        Perform some processing on image urls (perhaps removing size restrictions for
        dynamically generated images, etc.) and return the precessed URL.
        '''
        return url

    @classmethod
    def get_browser(cls, *args, **kwargs):
        '''
        Return a browser instance used to fetch documents from the web. By default
        it returns a `mechanize <http://wwwsearch.sourceforge.net/mechanize/>`_
        browser instance that supports cookies, ignores robots.txt, handles
        refreshes and has a mozilla firefox user agent.

        If your recipe requires that you login first, override this method
        in your subclass. For example, the following code is used in the New York
        Times recipe to login for full access::

            def get_browser(self):
                br = BasicNewsRecipe.get_browser()
                if self.username is not None and self.password is not None:
                    br.open('http://www.nytimes.com/auth/login')
                    br.select_form(name='login')
                    br['USERID']   = self.username
                    br['PASSWORD'] = self.password
                    br.submit()
                return br

        '''
        return browser(*args, **kwargs)

    def get_article_url(self, article):
        '''
        Override in a subclass to customize extraction of the :term:`URL` that points
        to the content for each article. Return the
        article URL. It is called with `article`, an object representing a parsed article
        from a feed. See `feedparser <http://www.feedparser.org/docs/>`_.
        By default it looks for the original link (for feeds syndicated via a
        service like feedburner or pheedo) and if found,
        returns that or else returns
        `article.link <http://www.feedparser.org/docs/reference-entry-link.html>`_.
        '''
        for key in article.keys():
            if key.endswith('_origlink'):
                url = article[key]
                if url and url.startswith('http://'):
                    return url
        return article.get('link',  None)

    def preprocess_html(self, soup):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        it is parsed for links and images.
        It can be used to do arbitrarily powerful pre-processing on the :term:`HTML`.
        It should return `soup` after processing it.

        `soup`: A `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        instance containing the downloaded :term:`HTML`.
        '''
        return soup

    def postprocess_html(self, soup, first_fetch):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, after
        it is parsed for links and images.
        It can be used to do arbitrarily powerful post-processing on the :term:`HTML`.
        It should return `soup` after processing it.

        :param soup: A `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_  instance containing the downloaded :term:`HTML`.
        :param first_fetch: True if this is the first page of an article.

        '''
        return soup

    def cleanup(self):
        '''
        Called after all articles have been download. Use it to do any cleanup like
        logging out of subscription sites, etc.
        '''
        pass

    def index_to_soup(self, url_or_raw, raw=False):
        '''
        Convenience method that takes an URL to the index page and returns
        a `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        of it.

        `url_or_raw`: Either a URL or the downloaded index page as a string
        '''
        if re.match(r'\w+://', url_or_raw):
            open_func = getattr(self.browser, 'open_novisit', self.browser.open)
            with closing(open_func(url_or_raw)) as f:
                _raw = f.read()
            if not _raw:
                raise RuntimeError('Could not fetch index from %s'%url_or_raw)
        else:
            _raw = url_or_raw
        if raw:
            return _raw
        if not isinstance(_raw, unicode) and self.encoding:
            if callable(self.encoding):
                _raw = self.encoding(_raw)
            else:
                _raw = _raw.decode(self.encoding, 'replace')
        massage = list(BeautifulSoup.MARKUP_MASSAGE)
        enc = 'cp1252' if callable(self.encoding) or self.encoding is None else self.encoding
        massage.append((re.compile(r'&(\S+?);'), lambda match:
            entity_to_unicode(match, encoding=enc)))
        return BeautifulSoup(_raw, markupMassage=massage)


    def sort_index_by(self, index, weights):
        '''
        Convenience method to sort the titles in `index` according to `weights`.
        `index` is sorted in place. Returns `index`.

        `index`: A list of titles.

        `weights`: A dictionary that maps weights to titles. If any titles
        in index are not in weights, they are assumed to have a weight of 0.
        '''
        weights = defaultdict(lambda : 0, weights)
        index.sort(cmp=lambda x, y: cmp(weights[x], weights[y]))
        return index

    def parse_index(self):
        '''
        This method should be implemented in recipes that parse a website
        instead of feeds to generate a list of articles. Typical uses are for
        news sources that have a "Print Edition" webpage that lists all the
        articles in the current print edition. If this function is implemented,
        it will be used in preference to :meth:`BasicNewsRecipe.parse_feeds`.

        It must return a list. Each element of the list must be a 2-element tuple
        of the form ``('feed title', list of articles)``.

        Each list of articles must contain dictionaries of the form::

            {
            'title'       : article title,
            'url'         : URL of print version,
            'date'        : The publication date of the article as a string,
            'description' : A summary of the article
            'content'     : The full article (can be an empty string). This is used by FullContentProfile
            }

        For an example, see the recipe for downloading `The Atlantic`.
        '''
        raise NotImplementedError

    def get_obfuscated_article(self, url):
        '''
        If you set `articles_are_obfuscated` this method is called with
        every article URL. It should return the path to a file on the filesystem
        that contains the article HTML. That file is processed by the recursive
        HTML fetching engine, so it can contain links to pages/images on the web.

        This method is typically useful for sites that try to make it difficult to
        access article content automatically. See for example the
        :module:`calibre.web.recipes.iht` recipe.
        '''
        raise NotImplementedError

    def populate_article_metadata(self, article, soup, first):
        '''
        Called when each HTML page belonging to article is downloaded.
        Intended to be used to get article metadata like author/summary/etc.
        from the parsed HTML (soup).
        :param article: A object of class :class:`calibre.web.feeds.Article`.
                       If you change the sumamry, remember to also change the
                       text_summary
        :param soup: Parsed HTML belonging to this article
        :param first: True iff the parsed HTML is the first page of the article.
        '''
        pass

    def postprocess_book(self, oeb, opts, log):
        '''
        Run any needed post processing on the parsed downloaded e-book.

        :param oeb: An OEBBook object
        :param opts: Conversion options
        '''
        pass

    def __init__(self, options, log, progress_reporter):
        '''
        Initialize the recipe.
        :param options: Parsed commandline options
        :param parser:  Command line option parser. Used to intelligently merge options.
        :param progress_reporter: A Callable that takes two arguments: progress (a number between 0 and 1) and a string message. The message should be optional.
        '''
        self.log = log
        if not isinstance(self.title, unicode):
            self.title = unicode(self.title, 'utf-8', 'replace')

        self.debug = options.verbose > 1
        self.output_dir = os.getcwd()
        self.verbose = options.verbose
        self.test = options.test
        self.username = options.username
        self.password = options.password
        self.lrf = options.lrf
        self.output_profile = options.output_profile
        self.touchscreen = getattr(self.output_profile, 'touchscreen', False)

        self.output_dir = os.path.abspath(self.output_dir)
        if options.test:
            self.max_articles_per_feed = 2
            self.simultaneous_downloads = min(4, self.simultaneous_downloads)

        if self.debug:
            self.verbose = True
        self.report_progress = progress_reporter

        if isinstance(self.feeds, basestring):
            self.feeds = eval(self.feeds)
            if isinstance(self.feeds, basestring):
                self.feeds = [self.feeds]

        if self.needs_subscription and (\
                self.username is None or self.password is None or \
                (not self.username and not self.password)):
            raise ValueError(_('The "%s" recipe needs a username and password.')%self.title)

        self.browser = self.get_browser()
        self.image_map, self.image_counter = {}, 1
        self.css_map = {}

        web2disk_cmdline = [ 'web2disk',
            '--timeout', str(self.timeout),
            '--max-recursions', str(self.recursions),
            '--delay', str(self.delay),
            ]

        if self.verbose:
            web2disk_cmdline.append('--verbose')

        if self.no_stylesheets:
            web2disk_cmdline.append('--dont-download-stylesheets')

        for reg in self.match_regexps:
            web2disk_cmdline.extend(['--match-regexp', reg])

        for reg in self.filter_regexps:
            web2disk_cmdline.extend(['--filter-regexp', reg])

        self.web2disk_options = web2disk_option_parser().parse_args(web2disk_cmdline)[0]
        for extra in ('keep_only_tags', 'remove_tags', 'preprocess_regexps',
                      'preprocess_html', 'remove_tags_after',
                      'remove_tags_before', 'is_link_wanted'):
            setattr(self.web2disk_options, extra, getattr(self, extra))
        self.web2disk_options.postprocess_html = self._postprocess_html
        self.web2disk_options.encoding = self.encoding

        if self.delay > 0:
            self.simultaneous_downloads = 1

        self.navbar = templates.TouchscreenNavBarTemplate() if self.touchscreen else templates.NavBarTemplate()
        self.failed_downloads = []
        self.partial_failures = []


    def _postprocess_html(self, soup, first_fetch, job_info):
        if self.no_stylesheets:
            for link in list(soup.findAll('link', type=re.compile('css')))+list(soup.findAll('style')):
                link.extract()
        head = soup.find('head')
        if not head:
            head = soup.find('body')
        if not head:
            head = soup.find(True)
        style = BeautifulSoup(u'<style type="text/css" title="override_css">%s</style>'%(self.template_css +'\n\n'+(self.extra_css if self.extra_css else ''))).find('style')
        head.insert(len(head.contents), style)
        if first_fetch and job_info:
            url, f, a, feed_len = job_info
            body = soup.find('body')
            if body is not None:
                templ = self.navbar.generate(False, f, a, feed_len,
                                             not self.has_single_feed,
                                             url, __appname__,
                                             center=self.center_navbar,
                                             extra_css=self.extra_css)
                elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8')).find('div')
                body.insert(0, elem)
        if self.remove_javascript:
            for script in list(soup.findAll('script')):
                script.extract()
            for o in soup.findAll(onload=True):
                del o['onload']

        for script in list(soup.findAll('noscript')):
            script.extract()
        for attr in self.remove_attributes:
            for x in soup.findAll(attrs={attr:True}):
                del x[attr]
        for base in list(soup.findAll(['base', 'iframe'])):
            base.extract()

        ans = self.postprocess_html(soup, first_fetch)
        try:
            article = self.feed_objects[f].articles[a]
        except:
            self.log.exception('Failed to get article object for postprocessing')
            pass
        else:
            self.populate_article_metadata(article, ans, first_fetch)
        return ans


    def download(self):
        '''
        Download and pre-process all articles from the feeds in this recipe.
        This method should be called only once on a particular Recipe instance.
        Calling it more than once will lead to undefined behavior.
        @return: Path to index.html
        @rtype: string
        '''
        try:
            res = self.build_index()
            self.report_progress(1, _('Download finished'))
            if self.failed_downloads:
                self.log.warning(_('Failed to download the following articles:'))
                for feed, article, debug in self.failed_downloads:
                    self.log.warning(article.title, 'from', feed.title)
                    self.log.debug(article.url)
                    self.log.debug(debug)
            if self.partial_failures:
                self.log.warning(_('Failed to download parts of the following articles:'))
                for feed, atitle, aurl, debug in self.partial_failures:
                    self.log.warning(atitle + _(' from ') + feed)
                    self.log.debug(aurl)
                    self.log.warning(_('\tFailed links:'))
                    for l, tb in debug:
                        self.log.warning(l)
                        self.log.debug(tb)
            return res
        finally:
            self.cleanup()

    def feeds2index(self, feeds):
        templ = templates.IndexTemplate()
        css = self.template_css + '\n\n' +(self.extra_css if self.extra_css else '')
        timefmt = self.timefmt
        if self.touchscreen:
            templ = templates.TouchscreenIndexTemplate()
            timefmt = '%A, %d %b %Y'
        return templ.generate(self.title, "mastheadImage.jpg", timefmt, feeds,
                              extra_css=css).render(doctype='xhtml')

    @classmethod
    def description_limiter(cls, src):
        if not src:
            return ''
        pos = cls.summary_length
        fuzz = 50
        si = src.find(';', pos)
        if si > 0 and si-pos > fuzz:
            si = -1
        gi = src.find('>', pos)
        if gi > 0 and gi-pos > fuzz:
            gi = -1
        npos = max(si, gi)
        if npos < 0:
            npos = pos
        ans = src[:npos+1]
        if len(ans) < len(src):
            return ans+u'\u2026' if isinstance(ans, unicode) else ans + '...'
        return ans



    def feed2index(self, feed):
        if feed.image_url is not None: # Download feed image
            imgdir = os.path.join(self.output_dir, 'images')
            if not os.path.isdir(imgdir):
                os.makedirs(imgdir)

            if self.image_map.has_key(feed.image_url):
                feed.image_url = self.image_map[feed.image_url]
            else:
                bn = urlparse.urlsplit(feed.image_url).path
                if bn:
                    bn = bn.rpartition('/')[-1]
                    if bn:
                        img = os.path.join(imgdir, 'feed_image_%d%s'%(self.image_counter, os.path.splitext(bn)))
                        try:
                            with nested(open(img, 'wb'), closing(self.browser.open(feed.image_url))) as (fi, r):
                                fi.write(r.read())
                            self.image_counter += 1
                            feed.image_url = img
                            self.image_map[feed.image_url] = img
                        except:
                            pass
            if isinstance(feed.image_url, str):
                feed.image_url = feed.image_url.decode(sys.getfilesystemencoding(), 'strict')


        templ = templates.FeedTemplate()
        css = self.template_css + '\n\n' +(self.extra_css if self.extra_css else '')

        if self.touchscreen:
            touchscreen_css = u'''
                    .summary_headline {
                        font-size:large; font-weight:bold; margin-top:0px; margin-bottom:0px;
                    }

                    .summary_byline {
                        font-size:small; margin-top:0px; margin-bottom:0px;
                    }

                    .summary_text {
                        margin-top:0px; margin-bottom:0px;
                    }

                    .feed {
                        font-family:sans-serif; font-weight:bold; font-size:larger;
                    }

                    .calibre_navbar {
                        font-family:monospace;
                    }
                    hr {
                        border-color:gray;
                        border-style:solid;
                        border-width:thin;
                    }

                    table.toc {
                        font-size:large;
                    }
                    td.article_count {
                        text-align:right;
                    }
            '''

            templ = templates.TouchscreenFeedTemplate()
            css = touchscreen_css + '\n\n' + (self.extra_css if self.extra_css else '')
        return templ.generate(feed, self.description_limiter,
                              extra_css=css).render(doctype='xhtml')


    def _fetch_article(self, url, dir, f, a, num_of_feeds):
        self.web2disk_options.browser = self.get_browser() if self.multithreaded_fetch else self.browser
        fetcher = RecursiveFetcher(self.web2disk_options, self.log,
                self.image_map, self.css_map,
                (url, f, a, num_of_feeds))
        fetcher.base_dir = dir
        fetcher.current_dir = dir
        fetcher.show_progress = False
        fetcher.image_url_processor = self.image_url_processor
        if self.multithreaded_fetch:
            fetcher.browser_lock = fetcher.DUMMY_LOCK
        res, path, failures = fetcher.start_fetch(url), fetcher.downloaded_paths, fetcher.failed_links
        if not res or not os.path.exists(res):
            raise Exception(_('Could not fetch article. Run with -vv to see the reason'))
        return res, path, failures

    def fetch_article(self, url, dir, f, a, num_of_feeds):
        return self._fetch_article(url, dir, f, a, num_of_feeds)

    def fetch_obfuscated_article(self, url, dir, f, a, num_of_feeds):
        path = os.path.abspath(self.get_obfuscated_article(url))
        url = ('file:'+path) if iswindows else ('file://'+path)
        return self._fetch_article(url, dir, f, a, num_of_feeds)

    def fetch_embedded_article(self, article, dir, f, a, num_of_feeds):
        templ = templates.EmbeddedContent()
        raw = templ.generate(article).render('html')
        with PersistentTemporaryFile('_feeds2disk.html') as pt:
            pt.write(raw)
            url = ('file:'+pt.name) if iswindows else ('file://'+pt.name)
        return self._fetch_article(url, dir,  f, a, num_of_feeds)


    def build_index(self):
        self.report_progress(0, _('Fetching feeds...'))
        try:
            feeds = feeds_from_index(self.parse_index(), oldest_article=self.oldest_article,
                                     max_articles_per_feed=self.max_articles_per_feed,
                                     log=self.log)
            self.report_progress(0, _('Got feeds from index page'))
        except NotImplementedError:
            feeds = self.parse_feeds()

        #feeds = FeedCollection(feeds)

        self.report_progress(0, _('Trying to download cover...'))
        self.download_cover()
        self.report_progress(0, _('Generating masthead...'))
        self.masthead_path = None

        try:
            murl = self.get_masthead_url()
        except:
            self.log.exception('Failed to get masthead url')
            murl = None

        if murl is not None:
            # Try downloading the user-supplied masthead_url
            # Failure sets self.masthead_path to None
            self.download_masthead(murl)
        if self.masthead_path is None:
            self.log.info("Synthesizing mastheadImage")
            self.masthead_path = os.path.join(self.output_dir, 'mastheadImage.jpg')
            try:
                self.default_masthead_image(self.masthead_path)
            except:
                self.log.exception('Failed to generate default masthead image')
                self.masthead_path = None

        if self.test:
            feeds = feeds[:2]
        self.has_single_feed = len(feeds) == 1

        if self.use_embedded_content is None:
            self.use_embedded_content = feeds[0].has_embedded_content()

        index = os.path.join(self.output_dir, 'index.html')

        html = self.feeds2index(feeds)
        with open(index, 'wb') as fi:
            fi.write(html)

        self.jobs = []

        if self.reverse_article_order:
            for feed in feeds:
                if hasattr(feed, 'reverse'):
                    feed.reverse()

        self.feed_objects = feeds
        for f, feed in enumerate(feeds):
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            if not os.path.isdir(feed_dir):
                os.makedirs(feed_dir)

            for a, article in enumerate(feed):
                if a >= self.max_articles_per_feed:
                    break
                art_dir = os.path.join(feed_dir, 'article_%d'%a)
                if not os.path.isdir(art_dir):
                    os.makedirs(art_dir)
                try:
                    url = self.print_version(article.url)
                except NotImplementedError:
                    url = article.url
                except:
                    self.log.exception('Failed to find print version for: '+article.url)
                    url = None
                if not url:
                    continue
                func, arg = (self.fetch_embedded_article, article) if self.use_embedded_content else \
                            ((self.fetch_obfuscated_article if self.articles_are_obfuscated \
                              else self.fetch_article), url)
                req = WorkRequest(func, (arg, art_dir, f, a, len(feed)),
                                      {}, (f, a), self.article_downloaded,
                                      self.error_in_article_download)
                req.feed = feed
                req.article = article
                req.feed_dir = feed_dir
                self.jobs.append(req)


        self.jobs_done = 0
        tp = ThreadPool(self.simultaneous_downloads)
        for req in self.jobs:
            tp.putRequest(req, block=True, timeout=0)


        self.report_progress(0, _('Starting download [%d thread(s)]...')%self.simultaneous_downloads)
        while True:
            try:
                tp.poll()
                time.sleep(0.1)
            except NoResultsPending:
                break

        #feeds.restore_duplicates()

        for f, feed in enumerate(feeds):
            html = self.feed2index(feed)
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            with open(os.path.join(feed_dir, 'index.html'), 'wb') as fi:
                fi.write(html)
        self.create_opf(feeds)
        self.report_progress(1, _('Feeds downloaded to %s')%index)

        return index

    def _download_cover(self):
        self.cover_path = None
        try:
            cu = self.get_cover_url()
        except Exception, err:
            cu = None
            self.log.error(_('Could not download cover: %s')%str(err))
            self.log.debug(traceback.format_exc())
        if cu is not None:
            ext = cu.split('/')[-1].rpartition('.')[-1]
            if '?' in ext:
                ext = ''
            ext = ext.lower() if ext and '/' not in ext else 'jpg'
            cpath = os.path.join(self.output_dir, 'cover.'+ext)
            if os.access(cu, os.R_OK):
                with open(cpath, 'wb') as cfile:
                    cfile.write(open(cu, 'rb').read())
            else:
                self.report_progress(1, _('Downloading cover from %s')%cu)
                with nested(open(cpath, 'wb'), closing(self.browser.open(cu))) as (cfile, r):
                    cfile.write(r.read())
            if ext.lower() == 'pdf':
                from calibre.ebooks.metadata.pdf import get_metadata
                stream = open(cpath, 'rb')
                mi = get_metadata(stream)
                cpath = None
                if mi.cover_data and mi.cover_data[1]:
                    cpath = os.path.join(self.output_dir,
                            'cover.'+mi.cover_data[0])
                    with open(cpath, 'wb') as f:
                        f.write(mi.cover_data[1])
            self.cover_path = cpath

    def download_cover(self):
        try:
            self._download_cover()
        except:
            self.log.exception('Failed to download cover')
            self.cover_path = None

    def _download_masthead(self, mu):
        ext = mu.rpartition('.')[-1]
        if '?' in ext:
            ext = ''
        ext = ext.lower() if ext else 'jpg'
        mpath = os.path.join(self.output_dir, 'masthead_source.'+ext)
        outfile = os.path.join(self.output_dir, 'mastheadImage.jpg')
        if os.access(mu, os.R_OK):
            with open(mpath, 'wb') as mfile:
                mfile.write(open(mu, 'rb').read())
        else:
            with nested(open(mpath, 'wb'), closing(self.browser.open(mu))) as (mfile, r):
                mfile.write(r.read())
            self.report_progress(1, _('Masthead image downloaded'))
        self.prepare_masthead_image(mpath, outfile)
        self.masthead_path = outfile
        if os.path.exists(mpath):
            os.remove(mpath)


    def download_masthead(self, url):
        try:
            self._download_masthead(url)
        except:
            self.log.exception("Failed to download supplied masthead_url")

    def default_cover(self, cover_file):
        '''
        Create a generic cover for recipes that dont have a cover
        '''
        try:
            from calibre.utils.magick_draw import create_cover_page, TextLine
            title = self.title if isinstance(self.title, unicode) else \
                    self.title.decode(preferred_encoding, 'replace')
            date = strftime(self.timefmt)
            lines = [TextLine(title, 44), TextLine(date, 32)]
            img_data = create_cover_page(lines, I('library.png'), output_format='jpg')
            cover_file.write(img_data)
            cover_file.flush()
        except:
            self.log.exception('Failed to generate default cover')
            return False
        return True

    def get_masthead_title(self):
        'Override in subclass to use something other than the recipe title'
        return self.title

    MI_WIDTH = 600
    MI_HEIGHT = 60

    def default_masthead_image(self, out_path):
        from calibre.ebooks.conversion.config import load_defaults
        from calibre.utils.fonts import fontconfig
        font_path = default_font = P('fonts/liberation/LiberationSerif-Bold.ttf')
        recs = load_defaults('mobi_output')
        masthead_font_family = recs.get('masthead_font', 'Default')

        if masthead_font_family != 'Default':
            masthead_font = fontconfig.files_for_family(masthead_font_family)
            # Assume 'normal' always in dict, else use default
            # {'normal': (path_to_font, friendly name)}
            if 'normal' in masthead_font:
                font_path = masthead_font['normal'][0]

        if not font_path or not os.access(font_path, os.R_OK):
            font_path = default_font

        try:
            from PIL import Image, ImageDraw, ImageFont
            Image, ImageDraw, ImageFont
        except ImportError:
            import Image, ImageDraw, ImageFont

        img = Image.new('RGB', (self.MI_WIDTH, self.MI_HEIGHT), 'white')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(font_path, 48)
        except:
            font = ImageFont.truetype(default_font, 48)
        text = self.get_masthead_title().encode('utf-8')
        width, height = draw.textsize(text, font=font)
        left = max(int((self.MI_WIDTH - width)/2.), 0)
        top = max(int((self.MI_HEIGHT - height)/2.), 0)
        draw.text((left, top), text, fill=(0,0,0), font=font)
        img.save(open(out_path, 'wb'), 'JPEG')

    def prepare_masthead_image(self, path_to_image, out_path):
        import calibre.utils.PythonMagickWand as pw
        from ctypes import byref
        from calibre import fit_image

        with pw.ImageMagick():
            img = pw.NewMagickWand()
            img2 = pw.NewMagickWand()
            frame = pw.NewMagickWand()
            p = pw.NewPixelWand()
            if img < 0 or img2 < 0 or p < 0 or frame < 0:
                raise RuntimeError('Out of memory')
            if not pw.MagickReadImage(img, path_to_image):
                severity = pw.ExceptionType(0)
                msg = pw.MagickGetException(img, byref(severity))
                raise IOError('Failed to read image from: %s: %s'
                        %(path_to_image, msg))
            pw.PixelSetColor(p, 'white')
            width, height = pw.MagickGetImageWidth(img),pw.MagickGetImageHeight(img)
            scaled, nwidth, nheight = fit_image(width, height, self.MI_WIDTH, self.MI_HEIGHT)
            if not pw.MagickNewImage(img2, width, height, p):
                raise RuntimeError('Out of memory')
            if not pw.MagickNewImage(frame,  self.MI_WIDTH, self.MI_HEIGHT, p):
                raise RuntimeError('Out of memory')
            if not pw.MagickCompositeImage(img2, img, pw.OverCompositeOp, 0, 0):
                raise RuntimeError('Out of memory')
            if scaled:
                if not pw.MagickResizeImage(img2, nwidth, nheight, pw.LanczosFilter,
                        0.5):
                    raise RuntimeError('Out of memory')
            left = int((self.MI_WIDTH - nwidth)/2.0)
            top = int((self.MI_HEIGHT - nheight)/2.0)
            if not pw.MagickCompositeImage(frame, img2, pw.OverCompositeOp,
                    left, top):
                raise RuntimeError('Out of memory')
            if not pw.MagickWriteImage(frame, out_path):
                raise RuntimeError('Failed to save image to %s'%out_path)

            pw.DestroyPixelWand(p)
            for x in (img, img2, frame):
                pw.DestroyMagickWand(x)

    def create_opf(self, feeds, dir=None):
        if dir is None:
            dir = self.output_dir
        mi = MetaInformation(self.short_title() + strftime(self.timefmt), [__appname__])
        mi.publisher = __appname__
        mi.author_sort = __appname__
        if self.output_profile.name == 'iPad':
            date_as_author = '%s, %s %s, %s' % (strftime('%A'), strftime('%B'), strftime('%d').lstrip('0'), strftime('%Y'))
            mi.authors = [date_as_author]
            mi.author_sort = strftime('%Y-%m-%d')
        mi.publication_type = 'periodical:'+self.publication_type
        mi.timestamp = nowf()
        mi.comments = self.description
        if not isinstance(mi.comments, unicode):
            mi.comments = mi.comments.decode('utf-8', 'replace')
        mi.pubdate = nowf()
        opf_path = os.path.join(dir, 'index.opf')
        ncx_path = os.path.join(dir, 'index.ncx')

        opf = OPFCreator(dir, mi)
        # Add mastheadImage entry to <guide> section
        mp = getattr(self, 'masthead_path', None)
        if mp is not None and os.access(mp, os.R_OK):
            from calibre.ebooks.metadata.opf2 import Guide
            ref = Guide.Reference(os.path.basename(self.masthead_path), os.getcwdu())
            ref.type = 'masthead'
            ref.title = 'Masthead Image'
            opf.guide.append(ref)

        manifest = [os.path.join(dir, 'feed_%d'%i) for i in range(len(feeds))]
        manifest.append(os.path.join(dir, 'index.html'))
        manifest.append(os.path.join(dir, 'index.ncx'))

        # Get cover
        cpath = getattr(self, 'cover_path', None)
        if cpath is None:
            pf = open(os.path.join(dir, 'cover.jpg'), 'wb')
            if self.default_cover(pf):
                cpath =  pf.name
        if cpath is not None and os.access(cpath, os.R_OK):
            opf.cover = cpath
            manifest.append(cpath)

        # Get masthead
        mpath = getattr(self, 'masthead_path', None)
        if mpath is not None and os.access(mpath, os.R_OK):
            manifest.append(mpath)

        opf.create_manifest_from_files_in(manifest)
        for mani in opf.manifest:
            if mani.path.endswith('.ncx'):
                mani.id = 'ncx'
            if mani.path.endswith('mastheadImage.jpg'):
                mani.id = 'masthead-image'

        entries = ['index.html']
        toc = TOC(base_path=dir)
        self.play_order_counter = 0
        self.play_order_map = {}

        def feed_index(num, parent):
            f = feeds[num]
            for j, a in enumerate(f):
                if getattr(a, 'downloaded', False):
                    adir = 'feed_%d/article_%d/'%(num, j)
                    auth = a.author
                    if not auth:
                        auth = None
                    desc = a.text_summary
                    if not desc:
                        desc = None
                    else:
                        desc = self.description_limiter(desc)
                    entries.append('%sindex.html'%adir)
                    po = self.play_order_map.get(entries[-1], None)
                    if po is None:
                        self.play_order_counter += 1
                        po = self.play_order_counter
                    parent.add_item('%sindex.html'%adir, None, a.title if a.title else _('Untitled Article'),
                                    play_order=po, author=auth, description=desc)
                    last = os.path.join(self.output_dir, ('%sindex.html'%adir).replace('/', os.sep))
                    for sp in a.sub_pages:
                        prefix = os.path.commonprefix([opf_path, sp])
                        relp = sp[len(prefix):]
                        entries.append(relp.replace(os.sep, '/'))
                        last = sp

                    if os.path.exists(last):
                        with open(last, 'rb') as fi:
                            src = fi.read().decode('utf-8')
                        soup = BeautifulSoup(src)
                        body = soup.find('body')
                        if body is not None:
                            prefix = '/'.join('..'for i in range(2*len(re.findall(r'link\d+', last))))
                            templ = self.navbar.generate(True, num, j, len(f),
                                            not self.has_single_feed,
                                            a.orig_url, __appname__, prefix=prefix,
                                            center=self.center_navbar)
                            elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8')).find('div')
                            body.insert(len(body.contents), elem)
                            with open(last, 'wb') as fi:
                                fi.write(unicode(soup).encode('utf-8'))
        if len(feeds) == 0:
            raise Exception('All feeds are empty, aborting.')

        if len(feeds) > 1:
            for i, f in enumerate(feeds):
                entries.append('feed_%d/index.html'%i)
                po = self.play_order_map.get(entries[-1], None)
                if po is None:
                    self.play_order_counter += 1
                    po = self.play_order_counter
                auth = getattr(f, 'author', None)
                if not auth:
                    auth = None
                desc = getattr(f, 'description', None)
                if not desc:
                    desc = None
                feed_index(i, toc.add_item('feed_%d/index.html'%i, None,
                    f.title, play_order=po, description=desc, author=auth))

        else:
            entries.append('feed_%d/index.html'%0)
            feed_index(0, toc)

        for i, p in enumerate(entries):
            entries[i] = os.path.join(dir, p.replace('/', os.sep))
        opf.create_spine(entries)
        opf.set_toc(toc)

        with nested(open(opf_path, 'wb'), open(ncx_path, 'wb')) as (opf_file, ncx_file):
            opf.render(opf_file, ncx_file)


    def article_downloaded(self, request, result):
        index = os.path.join(os.path.dirname(result[0]), 'index.html')
        if index != result[0]:
            if os.path.exists(index):
                os.remove(index)
            os.rename(result[0], index)
        a = request.requestID[1]

        article = request.article
        self.log.debug('Downloaded article:', article.title, 'from', article.url)
        article.orig_url = article.url
        article.url = 'article_%d/index.html'%a
        article.downloaded = True
        article.sub_pages  = result[1][1:]
        self.jobs_done += 1
        self.report_progress(float(self.jobs_done)/len(self.jobs),
            _(u'Article downloaded: %s')%repr(article.title))
        if result[2]:
            self.partial_failures.append((request.feed.title, article.title, article.url, result[2]))

    def error_in_article_download(self, request, traceback):
        self.jobs_done += 1
        self.log.error('Failed to download article:', request.article.title,
        'from', request.article.url)
        self.log.debug(traceback)
        self.log.debug('\n')
        self.report_progress(float(self.jobs_done)/len(self.jobs),
                _('Article download failed: %s')%repr(request.article.title))
        self.failed_downloads.append((request.feed, request.article, traceback))

    def parse_feeds(self):
        '''
        Create a list of articles from the list of feeds returned by :meth:`BasicNewsRecipe.get_feeds`.
        Return a list of :class:`Feed` objects.
        '''
        feeds = self.get_feeds()
        parsed_feeds = []
        for obj in feeds:
            if isinstance(obj, basestring):
                title, url = None, obj
            else:
                title, url = obj
            if url.startswith('feed://'):
                url = 'http'+url[4:]
            self.report_progress(0, _('Fetching feed')+' %s...'%(title if title else url))
            try:
                with closing(self.browser.open(url)) as f:
                    parsed_feeds.append(feed_from_xml(f.read(),
                                          title=title,
                                          log=self.log,
                                          oldest_article=self.oldest_article,
                                          max_articles_per_feed=self.max_articles_per_feed,
                                          get_article_url=self.get_article_url))
            except Exception, err:
                feed = Feed()
                msg = 'Failed feed: %s'%(title if title else url)
                feed.populate_from_preparsed_feed(msg, [])
                feed.description = repr(err)
                parsed_feeds.append(feed)
                self.log.exception(msg)


        remove = [f for f in parsed_feeds if len(f) == 0 and
                self.remove_empty_feeds]
        for f in remove:
            parsed_feeds.remove(f)

        return parsed_feeds

    @classmethod
    def tag_to_string(self, tag, use_alt=True, normalize_whitespace=True):
        '''
        Convenience method to take a
        `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        `Tag` and extract the text from it recursively, including any CDATA sections
        and alt tag attributes. Return a possibly empty unicode string.

        `use_alt`: If `True` try to use the alt attribute for tags that don't
        have any textual content

        `tag`: `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        `Tag`
        '''
        if not tag:
            return ''
        if isinstance(tag, basestring):
            return tag
        strings = []
        for item in tag.contents:
            if isinstance(item, (NavigableString, CData)):
                strings.append(item.string)
            elif isinstance(item, Tag):
                res = self.tag_to_string(item)
                if res:
                    strings.append(res)
                elif use_alt and item.has_key('alt'):
                    strings.append(item['alt'])
        ans = u''.join(strings)
        if normalize_whitespace:
            ans = re.sub(r'\s+', ' ', ans)
        return ans

    @classmethod
    def soup(cls, raw):
        entity_replace = [(re.compile(ur'&(\S+?);'), partial(entity_to_unicode,
                                                           exceptions=[]))]
        nmassage = list(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(entity_replace)
        return BeautifulSoup(raw, markupMassage=nmassage)

    @classmethod
    def adeify_images(cls, soup):
         '''
         If your recipe when converted to EPUB has problems with images when
         viewed in Adobe Digital Editions, call this method from within
         :method:`postprocess_html`.
         '''
         for item in soup.findAll('img'):
             for attrib in ['height','width','border','align','style']:
                 if item.has_key(attrib):
                    del item[attrib]
             oldParent = item.parent
             myIndex = oldParent.contents.index(item)
             item.extract()
             divtag = Tag(soup,'div')
             brtag  = Tag(soup,'br')
             oldParent.insert(myIndex,divtag)
             divtag.append(item)
             divtag.append(brtag)
         return soup


class CustomIndexRecipe(BasicNewsRecipe):

    def custom_index(self):
        '''
        Return the filesystem path to a custom HTML document that will serve as the index for
        this recipe. The index document will typically contain many `<a href="...">`
        tags that point to resources on the internet that should be downloaded.
        '''
        raise NotImplementedError

    def create_opf(self):
        mi = MetaInformation(self.title + strftime(self.timefmt), [__appname__])
        mi.publisher = __appname__
        mi.author_sort = __appname__
        mi = OPFCreator(self.output_dir, mi)
        mi.create_manifest_from_files_in([self.output_dir])
        mi.create_spine([os.path.join(self.output_dir, 'index.html')])
        with open(os.path.join(self.output_dir, 'index.opf'), 'wb') as opf_file:
            mi.render(opf_file)

    def download(self):
        index = os.path.abspath(self.custom_index())
        url = 'file:'+index if iswindows else 'file://'+index
        self.web2disk_options.browser = self.browser
        fetcher = RecursiveFetcher(self.web2disk_options, self.log)
        fetcher.base_dir = self.output_dir
        fetcher.current_dir = self.output_dir
        fetcher.show_progress = False
        res = fetcher.start_fetch(url)
        self.create_opf()
        return res

class AutomaticNewsRecipe(BasicNewsRecipe):

    keep_only_tags = [dict(name=['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]

    def fetch_embedded_article(self, article, dir, f, a, num_of_feeds):
        if self.use_embedded_content:
            self.web2disk_options.keep_only_tags = []
        return BasicNewsRecipe.fetch_embedded_article(self, article, dir, f, a, num_of_feeds)

class CalibrePeriodical(BasicNewsRecipe):

    #: Set this to the slug for the calibre periodical
    calibre_periodicals_slug = None

    LOG_IN = 'http://news.calibre-ebook.com/accounts/login'
    needs_subscription = True
    __author__ = 'calibre Periodicals'

    def get_browser(self):
        br = BasicNewsRecipe.get_browser(self)
        br.open(self.LOG_IN)
        br.select_form(name='login')
        br['username'] = self.username
        br['password'] = self.password
        raw = br.submit().read()
        if 'href="/my-account"' not in raw:
            raise LoginFailed(
                    _('Failed to log in, check your username and password for'
                    ' the calibre Periodicals service.'))

        return br

    def download(self):
        import cStringIO
        self.log('Fetching downloaded recipe')
        try:
            raw = self.browser.open_novisit(
                'http://news.calibre-ebook.com/subscribed_files/%s/0/temp.downloaded_recipe'
                % self.calibre_periodicals_slug
                    ).read()
        except Exception, e:
            if hasattr(e, 'getcode') and e.getcode() == 403:
                raise DownloadDenied(
                        _('You do not have permission to download this issue.'
                        ' Either your subscription has expired or you have'
                        ' exceeded the maximum allowed downloads for today.'))
            raise
        f = cStringIO.StringIO(raw)
        from calibre.utils.zipfile import ZipFile
        zf = ZipFile(f)
        zf.extractall()
        zf.close()
        from calibre.web.feeds.recipes import compile_recipe
        from glob import glob
        try:
            recipe = compile_recipe(open(glob('*.recipe')[0],
                'rb').read())
            self.conversion_options = recipe.conversion_options
        except:
            self.log.exception('Failed to compile downloaded recipe')
        return os.path.abspath('index.html')

