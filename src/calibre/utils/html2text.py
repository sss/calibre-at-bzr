#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""html2text: Turn HTML into equivalent Markdown-structured text."""
# Last upstream version before changes
#__version__ = "2.39"
__license__ = 'GPL 3'
__copyright__ = '''
Copyright (c) 2011, John Schember <john@nachtimwald.com>
(C) 2004-2008 Aaron Swartz <me@aaronsw.com>
'''
__contributors__ = ["Martin 'Joey' Schulze", "Ricardo Reyes", "Kevin Jay North"]

# TODO:
#   Support decoded entities with unifiable.

import re, sys, urllib, htmlentitydefs, codecs
import sgmllib
sgmllib.charref = re.compile('&#([xX]?[0-9a-fA-F]+)[^0-9a-fA-F]')

try: from textwrap import wrap
except: pass

# Use Unicode characters instead of their ascii psuedo-replacements
UNICODE_SNOB = 1

# Put the links after each paragraph instead of at the end.
LINKS_EACH_PARAGRAPH = 0

# Wrap long lines at position. 0 for no wrapping. (Requires Python 2.3.)
BODY_WIDTH = 0

# Don't show internal links (href="#local-anchor") -- corresponding link targets
# won't be visible in the plain text file anyway.
SKIP_INTERNAL_LINKS = True

### Entity Nonsense ###

def name2cp(k):
    if k == 'apos': return ord("'")
    if hasattr(htmlentitydefs, "name2codepoint"): # requires Python 2.3
        return htmlentitydefs.name2codepoint[k]
    else:
        k = htmlentitydefs.entitydefs[k]
        if k.startswith("&#") and k.endswith(";"): return int(k[2:-1]) # not in latin-1
        return ord(codecs.latin_1_decode(k)[0])

unifiable = {'rsquo':"'", 'lsquo':"'", 'rdquo':'"', 'ldquo':'"',
'copy':'(C)', 'mdash':'--', 'nbsp':' ', 'rarr':'->', 'larr':'<-', 'middot':'*',
'ndash':'-', 'oelig':'oe', 'aelig':'ae',
'agrave':'a', 'aacute':'a', 'acirc':'a', 'atilde':'a', 'auml':'a', 'aring':'a',
'egrave':'e', 'eacute':'e', 'ecirc':'e', 'euml':'e',
'igrave':'i', 'iacute':'i', 'icirc':'i', 'iuml':'i',
'ograve':'o', 'oacute':'o', 'ocirc':'o', 'otilde':'o', 'ouml':'o',
'ugrave':'u', 'uacute':'u', 'ucirc':'u', 'uuml':'u'}

unifiable_n = {}

for k in unifiable.keys():
    unifiable_n[name2cp(k)] = unifiable[k]

def charref(name):
    if name[0] in ['x','X']:
        c = int(name[1:], 16)
    else:
        c = int(name)

    if not UNICODE_SNOB and c in unifiable_n.keys():
        return unifiable_n[c]
    else:
        return unichr(c)

def entityref(c):
    if not UNICODE_SNOB and c in unifiable.keys():
        return unifiable[c]
    else:
        try: name2cp(c)
        except KeyError: return "&" + c
        else: return unichr(name2cp(c))

def replaceEntities(s):
    s = s.group(1)
    if s[0] == "#":
        return charref(s[1:])
    else: return entityref(s)

r_unescape = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")
def unescape(s):
    return r_unescape.sub(replaceEntities, s)

def fixattrs(attrs):
    # Fix bug in sgmllib.py
    if not attrs: return attrs
    newattrs = []
    for attr in attrs:
        newattrs.append((attr[0], unescape(attr[1])))
    return newattrs

### End Entity Nonsense ###

def onlywhite(line):
    """Return true if the line does only consist of whitespace characters."""
    for c in line:
        if c is not ' ' and c is not '  ':
            return c is ' '
    return line

def optwrap(text):
    """Wrap all paragraphs in the provided text."""
    if not BODY_WIDTH:
        return text

    assert wrap, "Requires Python 2.3."
    result = ''
    newlines = 0
    for para in text.split("\n"):
        if len(para) > 0:
            if para[0] is not ' ' and para[0] is not '-' and para[0] is not '*':
                for line in wrap(para, BODY_WIDTH):
                    result += line + "\n"
                result += "\n"
                newlines = 2
            else:
                if not onlywhite(para):
                    result += para + "\n"
                    newlines = 1
        else:
            if newlines < 2:
                result += "\n"
                newlines += 1
    return result

def hn(tag):
    if tag[0] == 'h' and len(tag) == 2:
        try:
            n = int(tag[1])
            if n in range(1, 10): return n
        except ValueError: return 0

class _html2text(sgmllib.SGMLParser):
    def __init__(self, out=None, baseurl=''):
        sgmllib.SGMLParser.__init__(self)

        if out is None: self.out = self.outtextf
        else: self.out = out
        self.outtext = u''
        self.quiet = 0
        self.p_p = 0
        self.outcount = 0
        self.start = 1
        self.space = 0
        self.astack = []
        self.list = []
        self.blockquote = 0
        self.pre = 0
        self.startpre = 0
        self.lastWasNL = 0
        self.abbr_title = None # current abbreviation definition
        self.abbr_data = None # last inner HTML (for abbr being defined)
        self.abbr_list = {} # stack of abbreviations to write later
        self.baseurl = baseurl

    def outtextf(self, s):
        self.outtext += s

    def close(self):
        sgmllib.SGMLParser.close(self)

        self.pbr()
        self.o('', 0, 'end')

        return self.outtext

    def handle_charref(self, c):
        self.o(charref(c))

    def handle_entityref(self, c):
        self.o(entityref(c))

    def unknown_starttag(self, tag, attrs):
        self.handle_tag(tag, attrs, 1)

    def unknown_endtag(self, tag):
        self.handle_tag(tag, None, 0)

    def handle_tag(self, tag, attrs, start):
        attrs = fixattrs(attrs)

        if hn(tag):
            self.p()
            if start: self.o(hn(tag)*"#" + ' ')

        if tag in ['p', 'div']: self.p()

        if tag == "br" and start: self.o("  \n")

        if tag == "hr" and start:
            self.p()
            self.o("* * *")
            self.p()

        if tag in ["head", "style", 'script']:
            if start: self.quiet += 1
            else: self.quiet -= 1

        if tag in ["body"]:
            self.quiet = 0 # sites like 9rules.com never close <head>

        if tag == "blockquote":
            if start:
                self.p(); self.o('> ', 0, 1); self.start = 1
                self.blockquote += 1
            else:
                self.blockquote -= 1
                self.p()

        if tag in ['em', 'i']: self.o("*")
        if tag in ['strong', 'b']: self.o("**")
        if tag == "code" and not self.pre: self.o('`') #TODO: `` `this` ``
        if tag == "abbr":
            if start:
                attrsD = {}
                for (x, y) in attrs: attrsD[x] = y
                attrs = attrsD

                self.abbr_title = None
                self.abbr_data = ''
                if attrs.has_key('title'):
                    self.abbr_title = attrs['title']
            else:
                if self.abbr_title != None:
                    self.abbr_list[self.abbr_data] = self.abbr_title
                    self.abbr_title = None
                self.abbr_data = ''

        if tag == "a":
            if start:
                attrsD = {}
                for (x, y) in attrs: attrsD[x] = y
                attrs = attrsD
                if attrs.has_key('href') and not (SKIP_INTERNAL_LINKS and attrs['href'].startswith('#')):
                    self.astack.append(attrs)
                    self.o("[")
                else:
                    self.astack.append(None)
            else:
                if self.astack:
                    a = self.astack.pop()
                    if a:
                        title = ''
                        if a.has_key('title'):
                            title = ' "%s"' % a['title']
                        self.o('](%s%s)' % (a['href'], title))

        if tag == "img" and start:
            attrsD = {}
            for (x, y) in attrs: attrsD[x] = y
            attrs = attrsD
            if attrs.has_key('src'):
                alt = attrs.get('alt', '')
                self.o("![")
                self.o(alt)
                title = ''
                if attrs.has_key('title'):
                    title = ' "%s"' % attrs['title']
                self.o('](%s%s)' % (attrs['src'], title))

        if tag == 'dl' and start: self.p()
        if tag == 'dt' and not start: self.pbr()
        if tag == 'dd' and start: self.o('    ')
        if tag == 'dd' and not start: self.pbr()

        if tag in ["ol", "ul"]:
            if start:
                self.list.append({'name':tag, 'num':0})
            else:
                if self.list: self.list.pop()

            self.p()

        if tag == 'li':
            if start:
                self.pbr()
                if self.list: li = self.list[-1]
                else: li = {'name':'ul', 'num':0}
                self.o("  "*len(self.list)) #TODO: line up <ol><li>s > 9 correctly.
                if li['name'] == "ul": self.o("* ")
                elif li['name'] == "ol":
                    li['num'] += 1
                    self.o(`li['num']`+". ")
                self.start = 1
            else:
                self.pbr()

        if tag in ["table", "tr"] and start: self.p()
        if tag == 'td': self.pbr()

        if tag == "pre":
            if start:
                self.startpre = 1
                self.pre = 1
            else:
                self.pre = 0
            self.p()

    def pbr(self):
        if self.p_p == 0: self.p_p = 1

    def p(self): self.p_p = 2

    def o(self, data, puredata=0, force=0):
        if self.abbr_data is not None: self.abbr_data += data

        if not self.quiet:
            if puredata and not self.pre:
                data = re.sub('\s+', ' ', data)
                if data and data[0] == ' ':
                    self.space = 1
                    data = data[1:]
            if not data and not force: return

            if self.startpre:
                #self.out(" :") #TODO: not output when already one there
                self.startpre = 0

            bq = (">" * self.blockquote)
            if not (force and data and data[0] == ">") and self.blockquote: bq += " "

            if self.pre:
                bq += "    "
                data = data.replace("\n", "\n"+bq)

            if self.start:
                self.space = 0
                self.p_p = 0
                self.start = 0

            if force == 'end':
                # It's the end.
                self.p_p = 0
                self.out("\n")
                self.space = 0

            if self.p_p:
                self.out(('\n'+bq)*self.p_p)
                self.space = 0

            if self.space:
                if not self.lastWasNL: self.out(' ')
                self.space = 0

            if self.abbr_list and force == "end":
                for abbr, definition in self.abbr_list.items():
                    self.out("  *[" + abbr + "]: " + definition + "\n")

            self.p_p = 0
            self.out(data)
            self.lastWasNL = data and data[-1] == '\n'
            self.outcount += 1

    def handle_data(self, data):
        if r'\/script>' in data: self.quiet -= 1
        self.o(data, 1)

    def unknown_decl(self, data): pass

def wrapwrite(text): sys.stdout.write(text.encode('utf8'))

def html2text_file(html, out=wrapwrite, baseurl=''):
    h = _html2text(out, baseurl)
    h.feed(html)
    h.feed("")
    return h.close()

def html2text(html, baseurl=''):
    return optwrap(html2text_file(html, None, baseurl))

if __name__ == "__main__":
    baseurl = ''
    if sys.argv[1:]:
        arg = sys.argv[1]
        if arg.startswith('http://') or arg.startswith('https://'):
            baseurl = arg
            j = urllib.urlopen(baseurl)
            try:
                from feedparser import _getCharacterEncoding as enc
                enc
            except ImportError:
                enc = lambda x, y: ('utf-8', 1)
            text = j.read()
            encoding = enc(j.headers, text)[0]
            if encoding == 'us-ascii': encoding = 'utf-8'
            data = text.decode(encoding)

        else:
            encoding = 'utf8'
            if len(sys.argv) > 2:
                encoding = sys.argv[2]
            data = open(arg, 'r').read().decode(encoding)
    else:
        data = sys.stdin.read().decode('utf8')
    wrapwrite(html2text(data, baseurl))

