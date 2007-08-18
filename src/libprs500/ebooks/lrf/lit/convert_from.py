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

import os, sys, shutil, glob, logging
from tempfile import mkdtemp
from subprocess import Popen, PIPE
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks import ConversionError
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file
from libprs500 import isosx, __appname__, setup_cli_handlers, iswindows
CLIT = 'clit'
if isosx and hasattr(sys, 'frameworks_dir'):
    CLIT = os.path.join(sys.frameworks_dir, CLIT)

def option_parser():
    return lrf_option_parser(
        '''Usage: %prog [options] mybook.lit\n\n'''
        '''%prog converts mybook.lit to mybook.lrf'''
        )

def generate_html(pathtolit, logger):
    if not os.access(pathtolit, os.R_OK):
        raise ConversionError, 'Cannot read from ' + pathtolit
    tdir = mkdtemp(prefix=__appname__+'_')
    os.rmdir(tdir)
    sep = r'\\' if iswindows else os.path.sep
    cmd = ' '.join([CLIT, '"'+pathtolit+'"', '"%s"'%(tdir+sep,)])
    logger.debug(cmd)
    p = Popen(cmd, shell=True, stderr=PIPE, stdout=PIPE)    
    logger.info(p.stdout.read())
    ret = p.wait()
    if ret != 0:
        if os.path.exists(tdir) and os.path.isdir(tdir):
            shutil.rmtree(tdir)
        err = p.stderr.read()
        raise ConversionError, err
    return tdir

def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('lit2lrf')
        setup_cli_handlers(logger, level)
    lit = os.path.abspath(os.path.expanduser(path))
    tdir = generate_html(lit, logger)
    try:
        l = glob.glob(os.path.join(tdir, '*toc*.htm*'))
        if not l:
            l = glob.glob(os.path.join(tdir, '*top*.htm*'))
        if not l:
            l = glob.glob(os.path.join(tdir, '*contents*.htm*'))
        if not l:
            l = glob.glob(os.path.join(tdir, '*.htm*'))
            if not l:
                l = glob.glob(os.path.join(tdir, '*.txt*')) # Some lit file apparently have .txt files in them
                if not l:
                    raise ConversionError('Conversion of lit to html failed. Cannot find html file.')
            maxsize, htmlfile = 0, None
            for c in l:
                sz = os.path.getsize(c)
                if sz > maxsize:
                    maxsize, htmlfile = sz, c
        else:
            htmlfile = l[0]
        if not options.output:
            ext = '.lrs' if options.lrs else '.lrf'
            options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
        options.output = os.path.abspath(os.path.expanduser(options.output))
        options.minimum_indent = 100  
        html_process_file(htmlfile, options, logger=logger)
    finally:
        shutil.rmtree(tdir)


def main(args=sys.argv, logger=None):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:            
        parser.print_help()
        print
        print 'No lit file specified'
        return 1
    process_file(args[1], options, logger)
    return 0        
        
            
if __name__ == '__main__':
    sys.exit(main())
