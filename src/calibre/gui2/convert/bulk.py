# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QString, SIGNAL

from calibre.gui2.convert.single import Config, sort_formats_by_preference, \
    GroupModel
from calibre.customize.ui import available_output_formats
from calibre.gui2 import ResizableDialog
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.gui2.convert.toc import TOCWidget
from calibre.gui2.convert import GuiRecommendations
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.config import prefs
from calibre.utils.logging import Log

class BulkConfig(Config):

    def __init__(self, parent, db, preferred_output_format=None):
        ResizableDialog.__init__(self, parent)

        self.setup_output_formats(db, preferred_output_format)
        self.db = db

        self.setup_pipeline()

        self.input_label.hide()
        self.input_formats.hide()

        self.connect(self.output_formats, SIGNAL('currentIndexChanged(QString)'),
                self.setup_pipeline)
        self.connect(self.groups, SIGNAL('activated(QModelIndex)'),
                self.show_pane)
        self.connect(self.groups, SIGNAL('clicked(QModelIndex)'),
                self.show_pane)
        self.connect(self.groups, SIGNAL('entered(QModelIndex)'),
                self.show_group_help)
        self.groups.setMouseTracking(True)


    def setup_pipeline(self, *args):
        oidx = self.groups.currentIndex().row()
        output_format = self.output_format

        input_path = 'dummy.epub'
        output_path = 'dummy.'+output_format
        log = Log()
        log.outputs = []
        self.plumber = Plumber(input_path, output_path, log)

        def widget_factory(cls):
            return cls(self.stack, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db)

        self.setWindowTitle(_('Bulk Convert'))
        lf = widget_factory(LookAndFeelWidget)
        ps = widget_factory(PageSetupWidget)
        sd = widget_factory(StructureDetectionWidget)
        toc = widget_factory(TOCWidget)

        output_widget = None
        name = self.plumber.output_plugin.name.lower().replace(' ', '_')
        try:
            output_widget = __import__('calibre.gui2.convert.'+name,
                        fromlist=[1])
            pw = output_widget.PluginWidget
            pw.ICON = I('back.svg')
            pw.HELP = _('Options specific to the output format.')
            output_widget = widget_factory(pw)
        except ImportError:
            pass

        while True:
            c = self.stack.currentWidget()
            if not c: break
            self.stack.removeWidget(c)

        widgets = [lf, ps, sd, toc]
        if output_widget is not None:
            widgets.append(output_widget)
        for w in widgets:
            self.stack.addWidget(w)
            self.connect(w, SIGNAL('set_help(PyQt_PyObject)'),
                    self.help.setPlainText)

        self._groups_model = GroupModel(widgets)
        self.groups.setModel(self._groups_model)

        idx = oidx if -1 < oidx < self._groups_model.rowCount() else 0
        self.groups.setCurrentIndex(self._groups_model.index(idx))
        self.stack.setCurrentIndex(idx)

    def setup_output_formats(self, db, preferred_output_format):
        if preferred_output_format:
            preferred_output_format = preferred_output_format.lower()
        output_formats = sorted(available_output_formats())
        output_formats.remove('oeb')
        preferred_output_format = preferred_output_format if \
            preferred_output_format and preferred_output_format \
            in output_formats else sort_formats_by_preference(output_formats,
                    prefs['output_format'])[0]
        self.output_formats.addItems(list(map(QString, [x.upper() for x in
            output_formats])))
        self.output_formats.setCurrentIndex(output_formats.index(preferred_output_format))

    def accept(self):
        recs = GuiRecommendations()
        for w in self._groups_model.widgets:
            if not w.pre_commit_check():
                return
            x = w.commit(save_defaults=False)
            recs.update(x)
        self._recommendations = recs
        ResizableDialog.accept(self)

