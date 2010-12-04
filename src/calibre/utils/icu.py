#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from calibre.constants import plugins

_icu = _collator = None

_none = u''
_none2 = b''

def load_icu():
    global _icu
    if _icu is None:
        _icu = plugins['icu'][0]
        if _icu is None:
            print plugins['icu'][1]
        else:
            if not _icu.ok:
                print 'icu not ok'
                _icu = None
    return _icu

def load_collator():
    global _collator
    from calibre.utils.localization import get_lang
    if _collator is None:
        icu = load_icu()
        if icu is not None:
            _collator = icu.Collator(get_lang())
    return _collator


def py_sort_key(obj):
    if not obj:
        return _none
    return obj.lower()

def icu_sort_key(collator, obj):
    if not obj:
        return _none2
    return collator.sort_key(obj.lower())

load_icu()
load_collator()
sort_key = py_sort_key if _icu is None or _collator is None else \
        partial(icu_sort_key, _collator)


def test(): # {{{
    # Data {{{
    german = '''
    Sonntag
Montag
Dienstag
Januar
Februar
März
Fuße
Fluße
Flusse
flusse
fluße
flüße
flüsse
'''
    german_good = '''
    Dienstag
Februar
flusse
Flusse
fluße
Fluße
flüsse
flüße
Fuße
Januar
März
Montag
Sonntag'''
    french = '''
dimanche
lundi
mardi
janvier
février
mars
déjà
Meme
deja
même
dejà
bpef
bœg
Boef
Mémé
bœf
boef
bnef
pêche
pèché
pêché
pêche
pêché'''
    french_good = '''
            bnef
        boef
        Boef
        bœf
        bœg
        bpef
        deja
        dejà
        déjà
        dimanche
        février
        janvier
        lundi
        mardi
        mars
        Meme
        Mémé
        même
        pèché
        pêche
        pêche
        pêché
        pêché'''
    # }}}

    def create(l):
        l = l.decode('utf-8').splitlines()
        return [x.strip() for x in l if x.strip()]

    german = create(german)
    c = _icu.Collator('de')
    print 'Sorted german:: (%s)'%c.actual_locale
    gs = list(sorted(german, key=c.sort_key))
    for x in gs:
        print '\t', x.encode('utf-8')
    if gs != create(german_good):
        print 'German failed'
        return
    print
    french = create(french)
    c = _icu.Collator('fr')
    print 'Sorted french:: (%s)'%c.actual_locale
    fs = list(sorted(french, key=c.sort_key))
    for x in fs:
        print '\t', x.encode('utf-8')
    if fs != create(french_good):
        print 'French failed (note that French fails with icu < 4.6 i.e. on windows and OS X)'
        return
# }}}

