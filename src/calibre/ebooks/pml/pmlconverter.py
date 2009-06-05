# -*- coding: utf-8 -*-

'''
Convert pml markup to and from html
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from htmlentitydefs import codepoint2name

from calibre.ebooks.pdb.ereader import image_name

PML_HTML_RULES = [
    (re.compile(r'\\p'), lambda match: '<br /><br style="page-break-after: always;" />'),
    (re.compile(r'\\x(?P<text>.+?)\\x', re.DOTALL), lambda match: '<h1 style="page-break-before: always;">%s</h1>' % match.group('text')),
    (re.compile(r'\\X(?P<val>[0-4])(?P<text>.+?)\\X[0-4]', re.DOTALL), lambda match: '<h%s style="page-break-before: always;">%s</h%s>' % (int(match.group('val')) + 1, match.group('text'), int(match.group('val')) + 1)),
    (re.compile(r'\\C\d=".+"'), lambda match: ''), # This should be made to create a TOC entry
    (re.compile(r'\\c(?P<text>.+?)\\c', re.DOTALL), lambda match: '<div style="text-align: center; display: block; margin: auto;">%s</div>' % match.group('text')),
    (re.compile(r'\\r(?P<text>.+?)\\r', re.DOTALL), lambda match: '<div style="text-align: right; display: block;">%s</div>' % match.group('text')),
    (re.compile(r'\\i(?P<text>.+?)\\i', re.DOTALL), lambda match: '<i>%s</i>' % match.group('text')),
    (re.compile(r'\\u(?P<text>.+?)\\u', re.DOTALL), lambda match: '<div style="text-decoration: underline;">%s</div>' % match.group('text')),
    (re.compile(r'\\o(?P<text>.+?)\\o', re.DOTALL), lambda match: '<del>%s</del>' % match.group('text')),
    (re.compile(r'\\v(?P<text>.+?)\\v', re.DOTALL), lambda match: '<!-- %s -->' % match.group('text')),
    (re.compile(r'\\t(?P<text>.+?)\\t', re.DOTALL), lambda match: '<div style="margin-left: 5%%;">%s</div>' % match.group('text')),
    (re.compile(r'\\T="(?P<val>\d+)%*"(?P<text>.+?)$', re.MULTILINE), lambda match: r'<div style="margin-left: %s%%;">%s</div>' % (match.group('val'), match.group('text'))),
    (re.compile(r'\\w="(?P<val>\d+)%"'), lambda match: '<hr width="%s%%" />' % match.group('val')),
    (re.compile(r'\\n'), lambda match: ''),
    (re.compile(r'\\s'), lambda match: ''),
    (re.compile(r'\\b(?P<text>.+?)\\b', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text')), # \b is deprecated; \B should be used instead.
    (re.compile(r'\\l(?P<text>.+?)\\l', re.DOTALL), lambda match: '<big>%s</big>' % match.group('text')),
    (re.compile(r'\\B(?P<text>.+?)\\B', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text')),
    (re.compile(r'\\Sp(?P<text>.+?)\\Sp', re.DOTALL), lambda match: '<sup>%s</sup>' % match.group('text')),
    (re.compile(r'\\Sb(?P<text>.+?)\\Sb', re.DOTALL), lambda match: '<sub>%s</sub>' % match.group('text')),
    (re.compile(r'\\k(?P<text>.+?)\\k', re.DOTALL), lambda match: '<small>%s</small>' % match.group('text')),
    (re.compile(r'\\a(?P<num>\d\d\d)'), lambda match: '&#%s;' % match.group('num')),
    (re.compile(r'\\U(?P<num>\d+)'), lambda match: '%s' % unichr(int(match.group('num'), 16))),
    (re.compile(r'\\m="(?P<name>.+?)"'), lambda match: '<img src="images/%s" />' % image_name(match.group('name')).strip('\x00')),
    (re.compile(r'\\q="(?P<target>#.+?)"(?P<text>.+?)\\q', re.DOTALL), lambda match: '<a href="%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile(r'\\Q="(?P<target>.+?)"'), lambda match: '<div id="%s"></div>' % match.group('target')),
    (re.compile(r'\\-'), lambda match: ''),
    (re.compile(r'\\Fn="(?P<target>.+?)"(?P<text>.+?)\\Fn'), lambda match: '<a href="#footnote-%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile(r'\\Sd="(?P<target>.+?)"(?P<text>.+?)\\Sd'), lambda match: '<a href="#sidebar-%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile(r'\\I'), lambda match: ''),
    
    # Sidebar and Footnotes
    (re.compile(r'<sidebar\s+id="(?P<target>.+?)">\s*(?P<text>.+?)\s*</sidebar>', re.DOTALL), lambda match: '<div id="sidebar-%s">%s</div>' % (match.group('target'), match.group('text'))),
    (re.compile(r'<footnote\s+id="(?P<target>.+?)">\s*(?P<text>.+?)\s*</footnote>', re.DOTALL), lambda match: '<div id="footnote-%s">%s</div>' % (match.group('target'), match.group('text'))),
    
    # eReader files are one paragraph per line.
    # This forces the lines to wrap properly.
    (re.compile('^(?P<text>.+)$', re.MULTILINE), lambda match: '<p>%s</p>' % match.group('text')),
    (re.compile('<p>[ ]*</p>'), lambda match: ''),
    
    # Remove unmatched plm codes.
    (re.compile(r'(?<=[^\\])\\[pxcriouvtblBk]'), lambda match: ''),
    (re.compile(r'(?<=[^\\])\\X[0-4]'), lambda match: ''),
    (re.compile(r'(?<=[^\\])\\Sp'), lambda match: ''),
    (re.compile(r'(?<=[^\\])\\Sb'), lambda match: ''),
    
    # Replace \\ with \.
    (re.compile(r'\\\\'), lambda match: '\\'),
]

def pml_to_html(pml):
    html = pml
    for rule in PML_HTML_RULES:
        html = rule[0].sub(rule[1], html)

    # Turn special characters into entities.
    cps = [ord(c) for c in set(html)]
    cps = set(cps).intersection(codepoint2name.keys()).difference([60, 62])
    for cp in cps:
        html = html.replace(unichr(cp), '&%s;' % codepoint2name[cp])

    return html

def footnote_sidebar_to_html(id, pml):
    html = '<div id="sidebar-%s"><dt>%s</dt></div><dd>%s</dd>' % (id, id, pml_to_html(pml))
    return html 

