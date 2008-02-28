#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
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
''''''

import sys, glob, mechanize, time, subprocess, os, re, shutil
from tempfile import NamedTemporaryFile
from xml.etree.ElementTree import parse, tostring, fromstring, Element
from BeautifulSoup import BeautifulSoup

# Load libprs500 from source copy
sys.path[0:1] = [os.path.dirname(os.path.dirname(os.getcwdu()))]

from libprs500.linux import entry_points

def browser():
    opener = mechanize.Browser()
    opener.set_handle_refresh(True)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    return opener

def update_manifest(src='libprs500.qhp'):
    root = parse(src).getroot()
    files = root.find('filterSection').find('files')
    files.clear()
    for f in glob.glob('*.html')+glob.glob('styles/*.css')+glob.glob('images/*'):
        if f.startswith('preview') or f in ('navtree.html', 'index.html'):
            continue
        files.append(fromstring('<file>%s</file>'%f))
    
    raw = tostring(root, 'UTF-8').replace('<file>', '\n            <file>')
    raw = raw.replace('</files>', '\n        </files>')
    raw = raw.replace('</filterSection>', '\n\n    </filterSection>')
    open(src, 'wb').write(raw+'\n')


def validate():
    br = browser()
    for f in glob.glob('*.html'):
        if f.startswith('preview-'):
            continue
        print 'Validating', f
        raw = open(f).read()
        br.open('http://validator.w3.org/#validate_by_input')
        br.form = tuple(br.forms())[2]
        br.form.set_value(raw, id='fragment')
        res = br.submit()
        soup = BeautifulSoup(res.read())
        if soup.find('div', id='result').find(id='congrats') is None:
            print 'Invalid HTML in', f
            t = NamedTemporaryFile()
            t.write(unicode(soup).encode('utf-8'))
            subprocess.call(('xdg-open', t.name))
            time.sleep(2)
            return
                        
def clean():
    for pat in ('preview-*.html', '*.qhc', '*.qch', 'cli-*.html', '~/.assistant/libprs500*'):
        for f in glob.glob(pat):
            f = os.path.abspath(os.path.expanduser(f))
            if os.path.exists(f):
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.unlink(f)
    return 0
                
def compile_help():
    QTDIR = '/usr/local/Trolltech/Qt-4.4.0-beta1'
    QTBIN = QTDIR + '/bin'
    QTLIB = QTDIR + '/lib'
    QCG = os.path.join(QTBIN, 'qcollectiongenerator')
    QTA = os.path.join(QTBIN, 'assistant')
    os.environ['LD_LIBRARY_PATH'] = QTLIB
    subprocess.check_call((QCG, 'libprs500.qhcp'))
    subprocess.call((QTA, '-collectionFile', 'libprs500.qhc'))
     

def populate_section(secref, items, src='libprs500.qhp'):
    root = parse(src).getroot()
    toc = root.find('filterSection').find('toc')
    sec = None
    
    for c in toc.findall('section'):
        if c.attrib['ref'] == secref:
            sec = c
            break
        
    attr = sec.attrib.copy()    
    sec.clear()
    sec.attrib = attr
    sec.text = '\n%16s'%' '
    secs = ['<section ref="%s" title="%s" />\n'%i for i in items]
    sec.tail = '\n\n%12s'%' '
    for i in secs:
        el = fromstring(i)
        sec.append(el)
        if secs.index(i) == len(secs)-1:
            el.tail = '\n%12s'%' '
        else:
            el.tail = '\n%16s'%' '
        
    
    raw = tostring(root, 'UTF-8')
    
    open(src, 'wb').write(raw)
    
def populate_faq(src='libprs500.qhp'):
    soup = BeautifulSoup(open('faq.html').read().decode('UTF-8'))
    items = []
    toc = soup.find('div', id="toc")
    for a in toc('a', href=True):
        items.append(('faq.html%s'%a['href'], a.string))
    
    populate_section('faq.html', items, src=src)

def generate_cli_docs(src='libprs500.qhp'):
    documented_cmds = []
    undocumented_cmds = []
        
    for script in entry_points['console_scripts']:
        module = script[script.index('=')+1:script.index(':')].strip()
        cmd = script[:script.index('=')].strip()
        module = __import__(module, fromlist=[module.split('.')[-1]])
        if hasattr(module, 'option_parser'):
            documented_cmds.append((cmd, getattr(module, 'option_parser')()))
        else:
            undocumented_cmds.append(cmd)
            
        documented_cmds.sort(cmp=lambda x, y: cmp(x[0], y[0]))
        undocumented_cmds.sort()
    
    
    def sanitize_text(txt):
        return txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
    for cmd, parser in documented_cmds:
        output = open('cli-%s.html'%cmd, 'wb')
        template = open('templates/basic.html', 'rb').read()
        usage = [sanitize_text(i) for i in parser.usage.replace('%prog', cmd).splitlines(True) if i]
        usage[0] = '<pre class="runcmd">%s</pre>'%usage[0]
        usage[1:] = [i.replace(cmd, '<span class="cmd">%s</span>'%cmd) for i in usage[1:]]
        usage = ''.join(usage).replace('\n', '<br />')
        body = ('\n<h1 class="documentHeading">%s</h1>\n'%cmd)+'<div>\n%s\n</div>'%usage
         
        
        groups = {}
        for grp in parser.option_groups:
            groups[(grp.title, grp.description)] = grp.option_list
            
        def group_html(title, description, option_list):
            res = []
            
            if title is not None:
                res.append('<tr><th colspan="2"><h3 class="subsectionHeading">%s</h3></th></tr>'%title)
            if description is not None:
                res.append('<tr><td colspan="2">%s<br />&nbsp;</td></tr>'%sanitize_text(description))
            for opt in option_list:
                shf = ' '.join(opt._short_opts)
                lgf = opt.get_opt_string()
                name = '%s<br />%s'%(lgf, shf)
                help = sanitize_text(opt.help) if opt.help else ''
                res.append('<tr><td class="option">%s</td><td>%s</td></tr>'%(name, help))
            return '\n'.join(res)
                
        
        gh = [group_html(None, None, parser.option_list)]
        for title, desc in groups.keys():
            olist = groups[(title, desc)]
            gh.append(group_html(title, desc, olist))
        
        if ''.join(gh).strip():
            body += '\n<h2 class="sectionHeading">[options]</h2>\n'
            body += '\n<table class="option_table">\n%s\n</table>\n'%'\n'.join(gh)
        output.write(template.replace('%body', body))
        
    uc_html = '\n<ul class="cmdlist">\n%s</ul>\n'%'\n'.join(\
                '<li>%s</li>\n'%i for i in undocumented_cmds)
    dc_html = '\n<ul class="cmdlist">\n%s</ul>\n'%'\n'.join(\
                '<li><a href="cli-%s.html">%s</a></li>\n'%(i[0], i[0]) for i in documented_cmds)
    
    body = '<h1 class="documentHeading">The Command Line Interface</h1>\n'
    body += '<div style="text-align:center"><img src="images/cli.png" alt="CLI" /></div>'
    body += '<p>%s</p>\n'%'<b class="cmd">libprs500</b> has a very comprehensive command line interface to perform most operations that can be performed by the GUI.'
    body += '<h2 class="sectionHeading">Documented commands</h2>\n'+dc_html
    body += '<h2 class="sectionHeading">Undocumented commands</h2>\n'+uc_html
    body += '<p>You can see usage for undocumented commands by executing them without arguments in a terminal</p>'
    open('cli-index.html', 'wb').write(template.replace('%body', body))
        
    
    cmds = [i[0] for i in documented_cmds]
    items = [('cli-%s.html'%i, i) for i in cmds]
    populate_section('cli-index.html', items, src=src)
    
    
    

def create_html_interface(src='libprs500.qhp'):
    root = parse(src).getroot()
    toc = root.find('filterSection').find('toc')
    
    def is_leaf(sec):
        return not sec.findall('section')
    
    
    def process_branch(branch, toplevel=False):
        parent = []
        for sec in branch.findall('section'):
            html = '<li class="||||">\n<a target="content" href="%s">%s</a>\n</li>\n'%(sec.attrib['ref'], sec.attrib['title'])
            lc = 'toplevel' if toplevel else 'nottoplevel'
            html=html.replace('||||', '%s ||||'%lc)
            
            type = 'file'
            if not is_leaf(sec):
                html = html.replace('</li>','%s\n</li>'%process_branch(sec))
                type = 'folder'
                
            parent.append(html.replace('||||', type))
        html = '\n'.join(parent)
        if toplevel:
            return html
        return '<ul>\n%s\n</ul>'%html
            
    tree = process_branch(toc, True)
    
    template = open('templates/navtree.html').read()
    open('navtree.html', 'wb').write(template.replace('%tree', tree)+'\n')        
        

def all(opts):
    generate_cli_docs()
    populate_faq()
    update_manifest()
    create_html_interface()
    compile_help()
    if opts.validate:
        validate()
    
    return 0

if __name__ == '__main__':
    from libprs500 import OptionParser
    parser = OptionParser()
    parser.add_option('--validate', default=False, action='store_true',
                      help='Validate all HTML files against their DTDs.')
    opts, args = parser.parse_args()
    
    if len(args) == 0:
        clean()
        sys.exit(all(opts))
    elif len(args) == 1:
        func = eval(args[0])
        fargs = []
        if args[0] == 'all':
            fargs = [opts]
        if func is None:
            print >>sys.stderr, 'Unknown target', sys.argv(1)
            sys.exit(1)
        sys.exit(func(*fargs))