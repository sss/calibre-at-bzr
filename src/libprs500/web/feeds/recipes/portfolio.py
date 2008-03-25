#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
portfolio.com
'''

from libprs500.web.feeds.news import BasicNewsRecipe

class Portfolio(BasicNewsRecipe):
    
    title                = 'Portfolio'
    use_embedded_content = True
    timefmt              = ' [%a, %b %d, %Y]'
    html2lrf_options     = ['--ignore-tables']
    
    feeds = [ 
                ('Business Travel', 'http://feeds.portfolio.com/portfolio/businesstravel'), 
                ('Careers', 'http://feeds.portfolio.com/portfolio/careers'), 
                ('Culture and Lifestyle', 'http://feeds.portfolio.com/portfolio/cultureandlifestyle'), 
                ('Executives','http://feeds.portfolio.com/portfolio/executives'), 
                ('News and Markets', 'http://feeds.portfolio.com/portfolio/news'), 
                ('Business Spin', 'http://feeds.portfolio.com/portfolio/businessspin'), 
                ('Capital', 'http://feeds.portfolio.com/portfolio/capital'), 
                ('Daily Brief', 'http://feeds.portfolio.com/portfolio/dailybrief'), 
                ('Market Movers', 'http://feeds.portfolio.com/portfolio/marketmovers'), 
                ('Mixed Media', 'http://feeds.portfolio.com/portfolio/mixedmedia'), 
                ('Odd Numbers', 'http://feeds.portfolio.com/portfolio/oddnumbers'), 
                ('Playbook', 'http://feeds.portfolio.com/portfolio/playbook'), 
                ('Tech Observer', 'http://feeds.portfolio.com/portfolio/thetechobserver'), 
                ('World According to ...', 'http://feeds.portfolio.com/portfolio/theworldaccordingto'), 
            ]