#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, uuid

from PyQt4.Qt import QPixmap, SIGNAL

from calibre.gui2 import choose_images, error_dialog, pixmap_to_data
from calibre.gui2.convert.metadata_ui import Ui_Form
from calibre.ebooks.metadata import authors_to_string, string_to_authors, \
        MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2.convert import Widget

class MetadataWidget(Widget, Ui_Form):

    TITLE = _('Metadata')
    ICON  = ':/images/dialog_information.svg'
    HELP  = _('Set the metadata. The output file will contain as much of this '
            'metadata as possible.')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, 'metadata', ['prefer_metadata_cover'])
        self.db, self.book_id = db, book_id
        self.cover_changed = False
        if self.db is not None:
            self.initialize_metadata_options()
        self.initialize_options(get_option, get_help, db, book_id)
        self.connect(self.cover_button, SIGNAL("clicked()"), self.select_cover)

    def initialize_metadata_options(self):
        self.initialize_combos()

        mi = self.db.get_metadata(self.book_id, index_is_id=True)
        self.title.setText(mi.title)
        if mi.publisher:
            self.publisher.setCurrentIndex(self.publisher.findText(mi.publisher))
        self.author_sort.setText(mi.author_sort if mi.author_sort else '')
        self.tags.setText(', '.join(mi.tags if mi.tags else []))
        self.tags.update_tags_cache(self.db.all_tags())
        self.comment.setText(mi.comments if mi.comments else '')
        if mi.series:
            self.series.setCurrentIndex(self.series.findText(mi.series))
        if mi.series_index is not None:
            try:
                self.series_index.setValue(mi.series_index)
            except:
                self.series_index.setValue(1.0)

        cover = self.db.cover(self.book_id, index_is_id=True)
        if cover:
            pm = QPixmap()
            pm.loadFromData(cover)
            if not pm.isNull():
                self.cover.setPixmap(pm)

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_authors:
            id, name = i
            name = authors_to_string([name.strip().replace('|', ',') for n in name.split(',')])
            self.author.addItem(name)

        au = self.db.authors(self.book_id, True)
        if not au:
            au = _('Unknown')
        au = ' & '.join([a.strip().replace('|', ',') for a in au.split(',')])
        self.author.setEditText(au)

    def initialize_series(self):
        all_series = self.db.all_series()
        all_series.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_series:
            id, name = i
            self.series.addItem(name)
        self.series.setCurrentIndex(-1)

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_publishers:
            id, name = i
            self.publisher.addItem(name)
        self.publisher.setCurrentIndex(-1)

    def get_title_and_authors(self):
        title = unicode(self.title.text()).strip()
        if not title:
            title = _('Unknown')
        authors = unicode(self.author.text()).strip()
        authors = string_to_authors(authors) if authors else [_('Unknown')]
        return title, authors

    def get_metadata(self):
        title, authors = self.get_title_and_authors()
        mi = MetaInformation(title, authors)
        publisher = unicode(self.publisher.text()).strip()
        if publisher:
            mi.publisher = publisher
        author_sort = unicode(self.author_sort.text()).strip()
        if author_sort:
            mi.author_sort = author_sort
        comments = unicode(self.comment.toPlainText()).strip()
        if comments:
            mi.comments = comments
        mi.series_index = float(self.series_index.value())
        if self.series.currentIndex() > -1:
            mi.series = unicode(self.series.currentText()).strip()
        tags = [t.strip() for t in unicode(self.tags.text()).strip().split(',')]
        if tags:
            mi.tags = tags

        return mi

    def select_cover(self):
        files = choose_images(self, 'change cover dialog',
                             _('Choose cover for ') + unicode(self.title.text()))
        if not files:
            return
        _file = files[0]
        if _file:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                d = error_dialog(self.window, _('Cannot read'),
                        _('You do not have permission to read the file: ') + _file)
                d.exec_()
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError, e:
                d = error_dialog(self.window, _('Error reading file'),
                        _("<p>There was an error reading from file: <br /><b>") + _file + "</b></p><br />"+str(e))
                d.exec_()
            if cover:
                pix = QPixmap()
                pix.loadFromData(cover)
                if pix.isNull():
                    d = error_dialog(self.window, _('Error reading file'),
                                      _file + _(" is not a valid picture"))
                    d.exec_()
                else:
                    self.cover_path.setText(_file)
                    self.cover.setPixmap(pix)
                    self.cover_changed = True
                    self.cpixmap = pix

    def get_recommendations(self):
        return {
                'prefer_metadata_cover':
                    bool(self.opt_prefer_metadata_cover.isChecked()),
                }


    def commit(self, save_defaults=False):
        '''
        Settings are stored in two attributes: `opf_file` and `cover_file`.
        Both may be None. Also returns a recommendation dictionary.
        '''
        recs = self.commit_options(save_defaults)
        self.user_mi = self.get_metadata()
        self.cover_file = self.opf_file = None
        if self.db is not None:
            self.db.set_metadata(self.book_id, self.user_mi)
            self.mi = self.db.get_metadata(self.book_id, index_is_id=True)
            self.mi.application_id = uuid.uuid4()
            opf = OPFCreator(os.getcwdu(), self.mi)
            self.opf_file = PersistentTemporaryFile('.opf')
            opf.render(self.opf_file)
            self.opf_file.close()
            if self.cover_changed:
                self.db.set_cover(self.book_id, pixmap_to_data(self.cover.pixmap()))
            cover = self.db.cover(self.book_id, index_is_id=True)
            if cover:
                cf = PersistentTemporaryFile('.jpeg')
                cf.write(cover)
                cf.close()
                self.cover_file = cf
        return recs

