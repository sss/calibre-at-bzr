#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QUrl

from calibre.gui2 import open_url
from calibre.gui2.actions import InterfaceAction

class HelpAction(InterfaceAction):

    name = 'Help'
    action_spec = (_('Help'), 'help.png', _('Browse the calibre User Manual'), _('F1'),)

    def genesis(self):
        self.qaction.triggered.connect(self.show_help)

    def show_help(self, *args):
        open_url(QUrl('http://calibre-ebook.com/user_manual'))



