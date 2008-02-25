##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import sys, logging, os

from libprs500 import setup_cli_handlers, OptionParser
from libprs500.ebooks import ConversionError
from libprs500.ebooks.lrf.meta import get_metadata
from libprs500.ebooks.lrf.parser import LRFDocument
from libprs500.ebooks.metadata.opf import OPFCreator

from libprs500.ebooks.lrf.objects import PageAttr, BlockAttr

class BlockStyle(object):
    
    def __init__(self, ba):
        self.ba = ba
        
    def __str__(self):
        ans = '.'+str(self.ba.id)+' {\n'
        if hasattr(self.ba, 'sidemargin'):
            margin = str(self.ba.sidemargin) + 'px'
            ans += '\tmargin-left: %(m)s; margin-right: %(m)s;\n'%dict(m=margin)
        if hasattr(self.ba, 'topskip'):
            ans += '\tmargin-top: %dpx;\n'%(self.ba.topskip,)
        if hasattr(self.ba, 'footskip'):
            ans += '\tmargin-bottom: %dpx;\n'%(self.ba.footskip,)
        if hasattr(self.ba, 'framewidth'):
            ans += '\tborder-width: %dpx;\n'%(self.ba.framewidth,)
            ans += '\tborder-style: solid;\n'
        if hasattr(self.ba, 'framecolor'):
            if self.ba.framecolor.a < 255:
                ans += '\tborder-color: %s;\n'%(self.ba.framecolor.to_html())
        if hasattr(self.ba, 'bgcolor'):
            if self.ba.bgcolor.a < 255:
                ans += '\tbackground-color: %s;\n'%(self.ba.bgcolor.to_html())
        #TODO: Fixed size blocks
        return ans + '}\n'
        

class LRFConverter(object):
    
    def __init__(self, document, opts, logger):
        self.lrf = document
        self.opts = opts
        self.output_dir = opts.out
        self.logger = logger
        logger.info('Parsing LRF...')
        self.lrf.parse()
        
        self.create_metadata()
        self.create_styles()
        
    def create_metadata(self):
        self.logger.info('Reading metadata...')
        mi = get_metadata(self.lrf)
        self.opf = OPFCreator(mi)
        
    def create_page_styles(self):
        self.page_css = ''
        for obj in self.lrf.objects.values():
            if isinstance(obj, PageAttr):
                selector = 'body.'+str(obj.id)
                self.page_css = selector + ' {\n'
                # TODO: Headers and footers
                self.page_css += '}\n'        
        
    def create_block_styles(self):
        self.block_css = ''
        for obj in self.lrf.objects.values():
            if isinstance(obj, BlockAttr):
                self.block_css += str(BlockStyle(obj))
                
        print self.block_css
                
    
    def create_styles(self):
        self.logger.info('Creating CSS stylesheet...')
        self.create_page_styles()
        self.create_block_styles()

def option_parser():
    parser = OptionParser(usage='%prog book.lrf')
    parser.add_option('--output-dir', '-o', default=None, help='Output directory in which to store created HTML files. If it does not exist, it is created. By default the current directory is used.', dest='out')
    parser.add_option('--verbose', default=False, action='store_true', dest='verbose')
    return parser

def process_file(lrfpath, opts, logger=None):
    if logger is None:
        level = logging.DEBUG if opts.verbose else logging.INFO
        logger = logging.getLogger('lrf2html')
        setup_cli_handlers(logger, level)
    if opts.out is None:
        opts.out = os.getcwdu()
    else:
        opts.out = os.path.abspath(opts.out)
        if not os.path.isdir(opts.out):
            raise ConversionError(opts.out + ' is not a directory')
    if not os.path.exists(opts.out):
        os.makedirs(opts.out)
        
    document = LRFDocument(open(lrfpath, 'rb'))
    conv = LRFConverter(document, opts, logger)    


def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    process_file(args[1], opts)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())