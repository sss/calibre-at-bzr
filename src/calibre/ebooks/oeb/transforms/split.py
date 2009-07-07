from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Splitting of the XHTML flows. Splitting can happen on page boundaries or can be
forces at "likely" locations to conform to size limitations. This transform
assumes a prior call to the flatcss transform.
'''

import os, math, functools, collections, re, copy

from lxml.etree import XPath as _XPath
from lxml import etree
from lxml.cssselect import CSSSelector

from calibre.ebooks.oeb.base import OEB_STYLES, XPNSMAP as NAMESPACES, \
        urldefrag, rewrite_links, urlunquote, barename, XHTML
from calibre.ebooks.epub import rules

XPath = functools.partial(_XPath, namespaces=NAMESPACES)

SPLIT_POINT_ATTR = 'csp'

def tostring(root):
    return etree.tostring(root, encoding='utf-8')

class SplitError(ValueError):

    def __init__(self, path, root):
        size = len(tostring(root))/1024.
        ValueError.__init__(self,
            _('Could not find reasonable point at which to split: '
                '%s Sub-tree size: %d KB')%
                            (path, size))

class Split(object):

    def __init__(self, split_on_page_breaks=True, page_breaks_xpath=None,
            max_flow_size=0):
        self.split_on_page_breaks = split_on_page_breaks
        self.page_breaks_xpath = page_breaks_xpath
        self.max_flow_size = max_flow_size
        self.page_break_selectors = None
        if self.page_breaks_xpath is not None:
            self.page_break_selectors = [(XPath(self.page_breaks_xpath), False)]

    def __call__(self, oeb, opts):
        self.oeb = oeb
        self.log = oeb.log
        self.opts = opts
        self.map = {}
        for item in list(self.oeb.manifest.items):
            if item.spine_position is not None and etree.iselement(item.data):
                self.split_item(item)

        self.fix_links()

    def split_item(self, item):
        page_breaks, page_break_ids = [], []
        if self.split_on_page_breaks:
            page_breaks, page_break_ids = self.find_page_breaks(item)

        splitter = FlowSplitter(item, page_breaks, page_break_ids,
                self.max_flow_size, self.oeb, self.opts)
        if splitter.was_split:
            am = splitter.anchor_map
            self.map[item.href] = collections.defaultdict(
                    am.default_factory, **am)

    def find_page_breaks(self, item):
        if self.page_break_selectors is None:
            self.page_break_selectors = set([])
            stylesheets = [x.data for x in self.oeb.manifest if x.media_type in
                    OEB_STYLES]
            for rule in rules(stylesheets):
                before = getattr(rule.style.getPropertyCSSValue(
                    'page-break-before'), 'cssText', '').strip().lower()
                after  = getattr(rule.style.getPropertyCSSValue(
                    'page-break-after'), 'cssText', '').strip().lower()
                try:
                    if before and before != 'avoid':
                        self.page_break_selectors.add((CSSSelector(rule.selectorText),
                            True))
                except:
                    pass
                try:
                    if after and after != 'avoid':
                        self.page_break_selectors.add((CSSSelector(rule.selectorText),
                            False))
                except:
                    pass

        page_breaks = set([])
        for selector, before in self.page_break_selectors:
            body = item.data.xpath('//h:body', namespaces=NAMESPACES)
            if not body:
                continue
            for elem in selector(body[0]):
                if elem not in body:
                    if before:
                        elem.set('pb_before', '1')
                    page_breaks.add(elem)

        for i, elem in enumerate(item.data.iter()):
            try:
                elem.set('pb_order', str(i))
            except TypeError: # Cant set attributes on comment nodes etc.
                continue

        page_breaks = list(page_breaks)
        page_breaks.sort(cmp=
              lambda x,y : cmp(int(x.get('pb_order')), int(y.get('pb_order'))))
        page_break_ids, page_breaks_ = [], []
        for i, x in enumerate(page_breaks):
            x.set('id', x.get('id', 'calibre_pb_%d'%i))
            id = x.get('id')
            page_breaks_.append((XPath('//*[@id="%s"]'%id),
                x.get('pb_before', False)))
            page_break_ids.append(id)

        for elem in item.data.iter():
            elem.attrib.pop('pb_order', False)
            if elem.get('pb_before', False):
                elem.attrib.pop('pb_before')

        return page_breaks_, page_break_ids

    def fix_links(self):
        '''
        Fix references to the split files in other content files.
        '''
        for item in self.oeb.manifest:
            if etree.iselement(item.data):
                self.current_item = item
                rewrite_links(item.data, self.rewrite_links)

    def rewrite_links(self, url):
        href, frag = urldefrag(url)
        href = self.current_item.abshref(href)
        if href in self.map:
            anchor_map = self.map[href]
            nhref = anchor_map[frag if frag else None]
            nhref = self.current_item.relhref(nhref)
            if frag:
                nhref = '#'.join((urlunquote(nhref), frag))

            return nhref
        return url



class FlowSplitter(object):
    'The actual splitting logic'

    def __init__(self, item, page_breaks, page_break_ids, max_flow_size, oeb,
            opts):
        self.item           = item
        self.oeb            = oeb
        self.opts           = opts
        self.log            = oeb.log
        self.page_breaks    = page_breaks
        self.page_break_ids = page_break_ids
        self.max_flow_size  = max_flow_size
        self.base           = item.href
        self.csp_counter    = 0

        base, ext = os.path.splitext(self.base)
        self.base = base.replace('%', '%%')+'_split_%d'+ext

        self.trees = [self.item.data.getroottree()]
        self.splitting_on_page_breaks = True
        if self.page_breaks:
            self.split_on_page_breaks(self.trees[0])
        self.splitting_on_page_breaks = False

        if self.max_flow_size > 0:
            lt_found = False
            self.log('\tLooking for large trees in %s...'%item.href)
            trees = list(self.trees)
            self.tree_map = {}
            for i, tree in enumerate(trees):
                size = len(tostring(tree.getroot()))
                if size > self.max_flow_size:
                    self.log('\tFound large tree #%d'%i)
                    lt_found = True
                    self.split_trees = []
                    self.split_to_size(tree)
                    self.tree_map[tree] = self.split_trees
            if not lt_found:
                self.log('\tNo large trees found')
            self.trees = []
            for x in trees:
                self.trees.extend(self.tree_map.get(x, [x]))

        self.was_split = len(self.trees) > 1
        if self.was_split:
            self.log('\tSplit into %d parts'%len(self.trees))
        self.commit()

    def split_on_page_breaks(self, orig_tree):
        ordered_ids = []
        for elem in orig_tree.xpath('//*[@id]'):
            id = elem.get('id')
            if id in self.page_break_ids:
                ordered_ids.append(self.page_breaks[self.page_break_ids.index(id)])

        self.trees = []
        tree = orig_tree
        for pattern, before in ordered_ids:
            elem = pattern(tree)
            if elem:
                self.log.debug('\t\tSplitting on page-break')
                before, after = self.do_split(tree, elem[0], before)
                self.trees.append(before)
                tree = after
        self.trees.append(tree)
        trees, ids = [], set([])
        for tree in self.trees:
            root = tree.getroot()
            if self.is_page_empty(root):
                discarded_ids = root.xpath('//*[@id]')
                for x in discarded_ids:
                    x = x.get('id')
                    if not x.startswith('calibre_'):
                        ids.add(x)
            else:
                if ids:
                    body = self.get_body(root)
                    if body is not None:
                        for x in ids:
                            body.insert(0, body.makeelement(XHTML('div'),
                                id=x, style='height:0pt'))
                ids = set([])
                trees.append(tree)
        self.trees = trees

    def get_body(self, root):
        body = root.xpath('//h:body', namespaces=NAMESPACES)
        if not body:
            return None
        return body[0]

    def adjust_split_point(self, root, path):
        '''
        Move the split point up its ancestor chain if it has no textual content
        before it. This handles the common case:
        <div id="chapter1"><h2>Chapter 1</h2>...</div> with a page break on the
        h2.
        '''
        sp = root.xpath(path)[0]
        while True:
            parent = sp.getparent()
            if barename(parent.tag) in ('body', 'html'):
                break
            if parent.text and parent.text.strip():
                break
            if parent.index(sp) > 0:
                break
            sp = parent

        npath = sp.getroottree().getpath(sp)

        if self.opts.verbose > 3 and npath != path:
            self.log.debug('\t\t\tMoved split point %s to %s'%(path, npath))


        return npath



    def do_split(self, tree, split_point, before):
        '''
        Split ``tree`` into a *before* and *after* tree at ``split_point``,
        preserving tag structure, but not duplicating any text.
        All tags that have had their text and tail
        removed have the attribute ``calibre_split`` set to 1.

        :param before: If True tree is split before split_point, otherwise after split_point
        :return: before_tree, after_tree
        '''
        path         = tree.getpath(split_point)
        tree, tree2  = copy.deepcopy(tree), copy.deepcopy(tree)
        root         = tree.getroot()
        root2        = tree2.getroot()
        body, body2  = map(self.get_body, (root, root2))
        path = self.adjust_split_point(root, path)
        split_point  = root.xpath(path)[0]
        split_point2 = root2.xpath(path)[0]


        def nix_element(elem, top=True):
            parent = elem.getparent()
            index = parent.index(elem)
            if top:
                parent.remove(elem)
            else:
                index = parent.index(elem)
                parent[index:index+1] = list(elem.iterchildren())

        # Tree 1
        hit_split_point = False
        for elem in list(body.iterdescendants(etree.Element)):
            if elem is split_point:
                hit_split_point = True
                if before:
                    x = elem.get('id', None)
                    nix_element(elem)

                continue
            if hit_split_point:
                x = elem.get('id', None)
                nix_element(elem)


        # Tree 2
        hit_split_point = False
        for elem in list(body2.iterdescendants(etree.Element)):
            if elem is split_point2:
                hit_split_point = True
                if not before:
                    x = elem.get('id', None)
                    nix_element(elem, top=False)
                continue
            if not hit_split_point:
                x = elem.get('id', None)
                nix_element(elem, top=False)
        body2.text = '\n'

        return tree, tree2

    def is_page_empty(self, root):
        body = self.get_body(root)
        if body is None:
            return False
        txt = re.sub(r'\s+', '',
                etree.tostring(body, method='text', encoding=unicode))
        if len(txt) > 4:
            return False
        for img in root.xpath('//h:img', namespaces=NAMESPACES):
            if img.get('style', '') != 'display:none':
                return False
        return True

    def split_text(self, text, root, size):
        self.log.debug('\t\t\tSplitting text of length: %d'%len(text))
        rest = text.replace('\r', '')
        parts = re.split('\n\n', rest)
        self.log.debug('\t\t\t\tFound %d parts'%len(parts))
        if max(map(len, parts)) > size:
            raise SplitError('Cannot split as file contains a <pre> tag '
                'with a very large paragraph', root)
        ans = []
        buf = ''
        for part in parts:
            if len(buf) + len(part) < size:
                buf += '\n\n'+part
            else:
                ans.append(buf)
                buf = part
        return ans


    def split_to_size(self, tree):
        self.log.debug('\t\tSplitting...')
        root = tree.getroot()
        # Split large <pre> tags
        for pre in list(root.xpath('//pre')):
            text = u''.join(pre.xpath('descendant::text()'))
            pre.text = text
            for child in list(pre.iterchildren()):
                pre.remove(child)
            if len(pre.text) > self.max_flow_size*0.5:
                frags = self.split_text(pre.text, root, int(0.2*self.max_flow_size))
                new_pres = []
                for frag in frags:
                    pre2 = copy.copy(pre)
                    pre2.text = frag
                    pre2.tail = u''
                    new_pres.append(pre2)
                new_pres[-1].tail = pre.tail
                p = pre.getparent()
                i = p.index(pre)
                p[i:i+1] = new_pres

        split_point, before = self.find_split_point(root)
        if split_point is None:
            raise SplitError(self.item.href, root)

        for t in self.do_split(tree, split_point, before):
            r = t.getroot()
            if self.is_page_empty(r):
                continue
            size = len(tostring(r))
            if size <= self.max_flow_size:
                self.split_trees.append(t)
                self.log.debug(
                    '\t\t\tCommitted sub-tree #%d (%d KB)'%(
                               len(self.split_trees), size/1024.))
            else:
                self.split_to_size(t)

    def find_split_point(self, root):
        '''
        Find the tag at which to split the tree rooted at `root`.
        Search order is:
            * Heading tags
            * <div> tags
            * <pre> tags
            * <hr> tags
            * <p> tags
            * <br> tags
            * <li> tags

        We try to split in the "middle" of the file (as defined by tag counts.
        '''
        def pick_elem(elems):
            if elems:
                elems = [i for i in elems if i.get(SPLIT_POINT_ATTR, '0') !=
                        '1']
                if elems:
                    i = int(math.floor(len(elems)/2.))
                    elems[i].set(SPLIT_POINT_ATTR, '1')
                    return elems[i]

        for path in (
                     '//*[re:match(name(), "h[1-6]", "i")]',
                     '/h:html/h:body/h:div',
                     '//h:pre',
                     '//h:hr',
                     '//h:p',
                     '//h:div',
                     '//h:br',
                     '//h:li',
                     ):
            elems = root.xpath(path, namespaces=NAMESPACES)
            elem = pick_elem(elems)
            if elem is not None:
                try:
                    XPath(elem.getroottree().getpath(elem))
                except:
                    continue
                return elem, True

        return None, True

    def commit(self):
        '''
        Commit all changes caused by the split. This removes the previously
        introduced ``calibre_split`` attribute and calculates an *anchor_map* for
        all anchors in the original tree. Internal links are re-directed. The
        original file is deleted and the split files are saved.
        '''
        if not self.was_split:
            return
        self.anchor_map = collections.defaultdict(lambda :self.base%0)
        self.files = []

        for i, tree in enumerate(self.trees):
            root = tree.getroot()
            self.files.append(self.base%i)
            for elem in root.xpath('//*[@id or @name]'):
                anchor = elem.get('id', '')
                if not anchor:
                    anchor = elem.get('name')
                self.anchor_map[anchor] = self.files[-1]
            for elem in root.xpath('//*[@%s]'%SPLIT_POINT_ATTR):
                elem.attrib.pop(SPLIT_POINT_ATTR, '0')

        spine_pos = self.item.spine_position

        for current, tree in zip(*map(reversed, (self.files, self.trees))):
            for a in tree.getroot().xpath('//h:a[@href]', namespaces=NAMESPACES):
                href = a.get('href').strip()
                if href.startswith('#'):
                    anchor = href[1:]
                    file = self.anchor_map[anchor]
                    file = self.item.relhref(file)
                    if file != current:
                        a.set('href', file+href)

            new_id = self.oeb.manifest.generate(id=self.item.id)[0]
            new_item = self.oeb.manifest.add(new_id, current,
                    self.item.media_type, data=tree.getroot())
            self.oeb.spine.insert(spine_pos, new_item, self.item.linear)

        if self.oeb.guide:
            for ref in self.oeb.guide.values():
                href, frag = urldefrag(ref.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag if frag else None]
                    if frag:
                        nhref = '#'.join((nhref, frag))
                    ref.href = nhref

        def fix_toc_entry(toc):
            if toc.href:
                href, frag = urldefrag(toc.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag if frag else None]
                    if frag:
                        nhref = '#'.join((nhref, frag))
                    toc.href = nhref
            for x in toc:
                fix_toc_entry(x)


        if self.oeb.toc:
            fix_toc_entry(self.oeb.toc)

        self.oeb.manifest.remove(self.item)
