#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Convert web feeds to LRF files.
'''
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.lrf.html.convert_from import process_file
from libprs500.web.feeds.main import option_parser as feeds_option_parser
from libprs500.web.feeds.main import run_recipe
from libprs500.ptempfile import PersistentTemporaryDirectory
from libprs500 import sanitize_file_name

import sys, os, time

def option_parser():
    parser = feeds_option_parser()
    parser.remove_option('--output-dir')
    parser.remove_option('--lrf')
    parser.subsume('FEEDS2DISK OPTIONS', _('Options to control the behavior of feeds2disk'))
    lrf_parser = lrf_option_parser('')
    lrf_parser.subsume('HTML2LRF OPTIONS', _('Options to control the behavior of html2lrf'))
    parser.merge(lrf_parser)
    return parser

def main(args=sys.argv, notification=None, handler=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    opts.lrf = True
    
    if len(args) != 2 and opts.feeds is None:
        parser.print_help()
        return 1
    
    recipe_arg = args[1] if len(args) > 1 else None
    
    tdir            = PersistentTemporaryDirectory('_feeds2lrf')
    opts.output_dir = tdir 
    
    recipe = run_recipe(opts, recipe_arg, parser, notification=notification, handler=handler)
    
    htmlfile = os.path.join(tdir, 'index.html')
    if not os.access(htmlfile, os.R_OK):
        raise RuntimeError(_('Fetching of recipe failed: ')+recipe_arg)
    
    lparser = lrf_option_parser('')
    ropts = lparser.parse_args(['html2lrf']+recipe.html2lrf_options)[0]
    parser.merge_options(ropts, opts)
    
    if not opts.output:
        ext = '.lrs' if opts.lrs else '.lrf'
        fname = recipe.title + time.strftime(recipe.timefmt)+ext
        opts.output = os.path.join(os.getcwd(), sanitize_file_name(fname))
    print 'Generating LRF...'
    process_file(htmlfile, opts)
    return 0

if __name__ == '__main__':
    sys.exit(main())