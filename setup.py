##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
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
import sys, re, os, shutil
sys.path.append('src')
islinux = not ('win32' in sys.platform or 'win64' in sys.platform or 'darwin' in sys.platform)
src = open('src/libprs500/__init__.py', 'rb').read()
VERSION = re.search(r'__version__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
APPNAME = re.search(r'__appname__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
print 'Setup', APPNAME, 'version:', VERSION

entry_points = {
        'console_scripts': [ \
                             'prs500    = libprs500.devices.prs500.cli.main:main', 
                             'lrf-meta  = libprs500.ebooks.lrf.meta:main', 
                             'rtf-meta  = libprs500.ebooks.metadata.rtf:main', 
                             'pdf-meta  = libprs500.ebooks.metadata.pdf:main', 
                             'lit-meta  = libprs500.ebooks.metadata.lit:main',
                             'opf-meta  = libprs500.ebooks.metadata.opf:main',
                             'epub-meta = libprs500.ebooks.metadata.epub:main',
                             'txt2lrf   = libprs500.ebooks.lrf.txt.convert_from:main', 
                             'html2lrf  = libprs500.ebooks.lrf.html.convert_from:main',
                             'markdown-libprs500  = libprs500.ebooks.markdown.markdown:main',
                             'lit2lrf   = libprs500.ebooks.lrf.lit.convert_from:main',
                             'epub2lrf  = libprs500.ebooks.lrf.epub.convert_from:main',
                             'rtf2lrf   = libprs500.ebooks.lrf.rtf.convert_from:main',
                             'web2disk  = libprs500.web.fetch.simple:main',
                             'web2lrf   = libprs500.ebooks.lrf.web.convert_from:main',
                             'pdf2lrf   = libprs500.ebooks.lrf.pdf.convert_from:main',
                             'any2lrf   = libprs500.ebooks.lrf.any.convert_from:main',
                             'lrf2lrs   = libprs500.ebooks.lrf.parser:main',
                             'lrs2lrf   = libprs500.ebooks.lrf.lrs.convert_from:main',
                             'isbndb    = libprs500.ebooks.metadata.isbndb:main',
                             'librarything = libprs500.ebooks.metadata.library_thing:main',
                             'lrf2html  = libprs500.ebooks.lrf.html.convert_to:main',                             
                           ], 
        'gui_scripts'    : [ 
                            APPNAME+' = libprs500.gui2.main:main',
                            'lrfviewer = libprs500.gui2.lrf_renderer.main:main',
                            ],
      }

if 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower():
    entry_points['console_scripts'].append('parallel = libprs500.parallel:main')

def _ep_to_script(ep, base='src'):
    return (base+os.path.sep+re.search(r'.*=\s*(.*?):', ep).group(1).replace('.', '/')+'.py').strip()


scripts = {
           'console' : [_ep_to_script(i) for i in entry_points['console_scripts']],
           'gui' : [_ep_to_script(i) for i in entry_points['gui_scripts']],
          }

def _ep_to_basename(ep):
    return re.search(r'\s*(.*?)\s*=', ep).group(1).strip()
basenames = {
             'console' : [_ep_to_basename(i) for i in entry_points['console_scripts']],
             'gui' : [_ep_to_basename(i) for i in entry_points['gui_scripts']],
            }

def _ep_to_module(ep):
    return re.search(r'.*=\s*(.*?)\s*:', ep).group(1).strip()
main_modules = {
                'console' : [_ep_to_module(i) for i in entry_points['console_scripts']],
                'gui' : [_ep_to_module(i) for i in entry_points['gui_scripts']],
               }

def _ep_to_function(ep):
    return ep[ep.rindex(':')+1:].strip()
main_functions = {
                'console' : [_ep_to_function(i) for i in entry_points['console_scripts']],
                'gui' : [_ep_to_function(i) for i in entry_points['gui_scripts']],
               }

if __name__ == '__main__':
    from setuptools import setup, find_packages
    import subprocess
    
    entry_points['console_scripts'].append('libprs500_postinstall = libprs500.linux:post_install')
    
    setup(
          name='libprs500', 
          packages = find_packages('src'), 
          package_dir = { '' : 'src' }, 
          version=VERSION, 
          author='Kovid Goyal', 
          author_email='kovid@kovidgoyal.net', 
          url = 'http://libprs500.kovidgoyal.net', 
          include_package_data = True,
          entry_points = entry_points, 
          zip_safe = True,
          description = 
                      """
                      Ebook management application.
                      """, 
          long_description = 
          """
          libprs500 is a ebook management application. It maintains an ebook library
          and allows for easy transfer of books from the library to an ebook reader.
          At the moment, it supports the `SONY Portable Reader`_.
          
          It can also convert various popular ebook formats into LRF, the native
          ebook format of the SONY Reader.
          
          For screenshots: https://libprs500.kovidgoyal.net/wiki/Screenshots
          
          For installation/usage instructions please see 
          https://libprs500.kovidgoyal.net/wiki/WikiStart#Installation
          
          For SVN access: svn co https://svn.kovidgoyal.net/code/libprs500
          
            .. _SONY Portable Reader: http://Sony.com/reader
            .. _USB: http://www.usb.org  
          """, 
          license = 'GPL', 
          classifiers = [
            'Development Status :: 4 - Beta', 
            'Environment :: Console', 
            'Environment :: X11 Applications :: Qt', 
            'Intended Audience :: Developers', 
            'Intended Audience :: End Users/Desktop', 
            'License :: OSI Approved :: GNU General Public License (GPL)', 
            'Natural Language :: English', 
            'Operating System :: POSIX :: Linux', 
            'Programming Language :: Python', 
            'Topic :: Software Development :: Libraries :: Python Modules', 
            'Topic :: System :: Hardware :: Hardware Drivers'
            ]
         )
    
    if 'develop' in ' '.join(sys.argv) and islinux:
        subprocess.check_call('libprs500_postinstall', shell=True)
