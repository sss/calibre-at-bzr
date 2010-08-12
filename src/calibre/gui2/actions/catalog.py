#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil

from PyQt4.Qt import QModelIndex

from calibre.gui2 import error_dialog, Dispatcher, choose_dir
from calibre.gui2.tools import generate_catalog
from calibre.utils.config import dynamic

class GenerateCatalogAction(object):

    def generate_catalog(self):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) < 2:
            rows = xrange(self.library_view.model().rowCount(QModelIndex()))
        ids = map(self.library_view.model().id, rows)

        dbspec = None
        if not ids:
            return error_dialog(self, _('No books selected'),
                    _('No books selected to generate catalog for'),
                    show=True)

        # Calling gui2.tools:generate_catalog()
        ret = generate_catalog(self, dbspec, ids, self.device_manager.device)
        if ret is None:
            return

        func, args, desc, out, sync, title = ret

        fmt = os.path.splitext(out)[1][1:].upper()
        job = self.job_manager.run_job(
                Dispatcher(self.catalog_generated), func, args=args,
                    description=desc)
        job.catalog_file_path = out
        job.fmt = fmt
        job.catalog_sync, job.catalog_title = sync, title
        self.status_bar.show_message(_('Generating %s catalog...')%fmt)

    def catalog_generated(self, job):
        if job.result:
            # Search terms nulled catalog results
            return error_dialog(self, _('No books found'),
                    _("No books to catalog\nCheck exclude tags"),
                    show=True)
        if job.failed:
            return self.job_exception(job)
        id = self.library_view.model().add_catalog(job.catalog_file_path, job.catalog_title)
        self.library_view.model().reset()
        if job.catalog_sync:
            sync = dynamic.get('catalogs_to_be_synced', set([]))
            sync.add(id)
            dynamic.set('catalogs_to_be_synced', sync)
        self.status_bar.show_message(_('Catalog generated.'), 3000)
        self.sync_catalogs()
        if job.fmt not in ['EPUB','MOBI']:
            export_dir = choose_dir(self, _('Export Catalog Directory'),
                    _('Select destination for %s.%s') % (job.catalog_title, job.fmt.lower()))
            if export_dir:
                destination = os.path.join(export_dir, '%s.%s' % (job.catalog_title, job.fmt.lower()))
                shutil.copyfile(job.catalog_file_path, destination)


