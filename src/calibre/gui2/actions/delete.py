#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.delete_matching_from_device import DeleteMatchingFromDeviceDialog
from calibre.gui2.dialogs.confirm_delete import confirm

class DeleteAction(object):

    def _get_selected_formats(self, msg):
        from calibre.gui2.dialogs.select_formats import SelectFormats
        fmts = self.library_view.model().db.all_formats()
        d = SelectFormats([x.lower() for x in fmts], msg, parent=self)
        if d.exec_() != d.Accepted:
            return None
        return d.selected_formats

    def _get_selected_ids(self, err_title=_('Cannot delete')):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, err_title, _('No book selected'))
            d.exec_()
            return set([])
        return set(map(self.library_view.model().id, rows))

    def delete_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            _('Choose formats to be deleted'))
        if not fmts:
            return
        for id in ids:
            for fmt in fmts:
                self.library_view.model().db.remove_format(id, fmt,
                        index_is_id=True, notify=False)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())
        if ids:
            self.tags_view.recount()

    def delete_all_but_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            '<p>'+_('Choose formats <b>not</b> to be deleted'))
        if fmts is None:
            return
        for id in ids:
            bfmts = self.library_view.model().db.formats(id, index_is_id=True)
            if bfmts is None:
                continue
            bfmts = set([x.lower() for x in bfmts.split(',')])
            rfmts = bfmts - set(fmts)
            for fmt in rfmts:
                self.library_view.model().db.remove_format(id, fmt,
                        index_is_id=True, notify=False)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())
        if ids:
            self.tags_view.recount()

    def remove_matching_books_from_device(self, *args):
        if not self.device_manager.is_device_connected:
            d = error_dialog(self, _('Cannot delete books'),
                             _('No device is connected'))
            d.exec_()
            return
        ids = self._get_selected_ids()
        if not ids:
            #_get_selected_ids shows a dialog box if nothing is selected, so we
            #do not need to show one here
            return
        to_delete = {}
        some_to_delete = False
        for model,name in ((self.memory_view.model(), _('Main memory')),
                           (self.card_a_view.model(), _('Storage Card A')),
                           (self.card_b_view.model(), _('Storage Card B'))):
            to_delete[name] = (model, model.paths_for_db_ids(ids))
            if len(to_delete[name][1]) > 0:
                some_to_delete = True
        if not some_to_delete:
            d = error_dialog(self, _('No books to delete'),
                             _('None of the selected books are on the device'))
            d.exec_()
            return
        d = DeleteMatchingFromDeviceDialog(self, to_delete)
        if d.exec_():
            paths = {}
            ids = {}
            for (model, id, path) in d.result:
                if model not in paths:
                    paths[model] = []
                    ids[model] = []
                paths[model].append(path)
                ids[model].append(id)
            for model in paths:
                job = self.remove_paths(paths[model])
                self.delete_memory[job] = (paths[model], model)
                model.mark_for_deletion(job, ids[model], rows_are_ids=True)
            self.status_bar.show_message(_('Deleting books from device.'), 1000)

    def delete_covers(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        for id in ids:
            self.library_view.model().db.remove_cover(id)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())

    def delete_books(self, *args):
        '''
        Delete selected books from device or library.
        '''
        view = self.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        if self.stack.currentIndex() == 0:
            if not confirm('<p>'+_('The selected books will be '
                                   '<b>permanently deleted</b> and the files '
                                   'removed from your computer. Are you sure?')
                                +'</p>', 'library_delete_books', self):
                return
            ci = view.currentIndex()
            row = None
            if ci.isValid():
                row = ci.row()
            ids_deleted = view.model().delete_books(rows)
            for v in (self.memory_view, self.card_a_view, self.card_b_view):
                if v is None:
                    continue
                v.model().clear_ondevice(ids_deleted)
            if row is not None:
                ci = view.model().index(row, 0)
                if ci.isValid():
                    view.set_current_row(row)
        else:
            if not confirm('<p>'+_('The selected books will be '
                                   '<b>permanently deleted</b> '
                                   'from your device. Are you sure?')
                                +'</p>', 'device_delete_books', self):
                return
            if self.stack.currentIndex() == 1:
                view = self.memory_view
            elif self.stack.currentIndex() == 2:
                view = self.card_a_view
            else:
                view = self.card_b_view
            paths = view.model().paths(rows)
            job = self.remove_paths(paths)
            self.delete_memory[job] = (paths, view.model())
            view.model().mark_for_deletion(job, rows)
            self.status_bar.show_message(_('Deleting books from device.'), 1000)

