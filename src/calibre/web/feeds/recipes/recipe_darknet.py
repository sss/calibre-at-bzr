__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch darknet.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class darknet(BasicNewsRecipe):

    title = 'darknet'
    description = 'Ethical hacking and security news'
    __author__ = 'Oliver Niesner'
    language = 'en'

    use_embedded_content   = False
    timefmt = ' [%b %d %Y]'
    max_articles_per_feed = 40
    no_stylesheets = True
    oldest_article = 180

    remove_tags = [dict(id='navi_top'),
		   dict(id='navi_bottom'),
		   dict(id='logo'),
		   dict(id='login_suche'),
		   dict(id='navi_login'),
		   dict(id='breadcrumb'),
		   dict(id='subtitle'),
		   dict(id='bannerzone'),
		   dict(name='span', attrs={'class':'rsaquo'}),
		   dict(name='span', attrs={'class':'next'}),
		   dict(name='span', attrs={'class':'prev'}),
		   dict(name='div', attrs={'class':'news_logo'}),
		   dict(name='div', attrs={'class':'nextprev'}),
		   dict(name='p', attrs={'class':'news_option'}),
		   dict(name='p', attrs={'class':'news_foren'})]
    remove_tags_after = [dict(name='div', attrs={'class':'entrybody'})]

    feeds =  [ ('darknet', 'http://feedproxy.google.com/darknethackers') ]



