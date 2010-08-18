#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.actions import InterfaceAction

class EditCollectionsAction(InterfaceAction):

    name = 'Edit Collections'
    action_spec = (_('Manage collections'), None, None, None)

    def location_selected(self, loc):
        enabled = loc != 'library'
        self.qaction.setEnabled(enabled)
        self.qaction.triggered.connect(self.edit_collections)

    def edit_collections(self, *args):
        oncard = None
        cv = self.gui.current_view()
        if cv is self.gui.card_a_view:
            oncard = 'carda'
        if cv is self.gui.card_b_view:
            oncard = 'cardb'
        self.gui.iactions['Edit Metadata'].edit_device_collections(cv,
                oncard=oncard)

