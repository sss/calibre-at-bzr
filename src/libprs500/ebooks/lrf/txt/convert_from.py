__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Convert .txt files to .lrf
"""
import os, sys, codecs, logging

from libprs500.ptempfile import PersistentTemporaryFile
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks import ConversionError
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file
from libprs500.ebooks.markdown import markdown
from libprs500 import setup_cli_handlers

def option_parser():
    parser = lrf_option_parser('''Usage: %prog [options] mybook.txt\n\n'''
        '''%prog converts mybook.txt to mybook.lrf''')
    parser.add_option('--debug-html-generation', action='store_true', default=False,
                      dest='debug_html_generation', help='Print generated HTML to stdout and quit.')
    return parser
    

def generate_html(txtfile, encoding, logger):
    '''
    Convert txtfile to html and return a PersistentTemporaryFile object pointing
    to the file with the HTML.
    '''
    enc = encoding
    if not encoding:
        encodings = ['cp1252', 'latin-1', 'utf8', 'iso-8859-1', 'koi8_r', 'koi8_u']
        txt, enc = None, None
        for encoding in encodings:
            try:
                txt = codecs.open(txtfile, 'rb', encoding).read()
            except UnicodeDecodeError:
                continue
            enc = encoding
            break
        if txt == None:
            raise ConversionError, 'Could not detect encoding of %s'%(txtfile,)
    else:
        txt = codecs.open(txtfile, 'rb', enc).read()
    
    logger.info('Converting text to HTML...')
    md = markdown.Markdown(
                       extensions=['footnotes', 'tables', 'toc'],
                       safe_mode=False,
                       )
    html = md.convert(txt)
    p = PersistentTemporaryFile('.html', dir=os.path.dirname(txtfile))
    p.close()
    codecs.open(p.name, 'wb', 'utf8').write(html)
    return p
        
def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('txt2lrf')
        setup_cli_handlers(logger, level)
    txt = os.path.abspath(os.path.expanduser(path))
    if not hasattr(options, 'debug_html_generation'):
        options.debug_html_generation = False
    htmlfile = generate_html(txt, options.encoding, logger)
    options.encoding = 'utf-8'
    if not options.debug_html_generation:
        options.force_page_break = 'h2'
        if not options.output:
            ext = '.lrs' if options.lrs else '.lrf'
            options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
        options.output = os.path.abspath(os.path.expanduser(options.output))
        if not options.title:
            options.title = os.path.splitext(os.path.basename(path))[0]
        html_process_file(htmlfile.name, options, logger)
    else:
        print open(htmlfile.name, 'rb').read()        

def main(args=sys.argv, logger=None):
    parser = option_parser()    
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No txt file specified'
        return 1
    process_file(args[1], options, logger)
    return 0

if __name__ == '__main__':
    sys.exit(main())