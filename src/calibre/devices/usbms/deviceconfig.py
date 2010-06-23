# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.utils.config import Config, ConfigProxy


class DeviceConfig(object):

    HELP_MESSAGE = _('Configure Device')
    EXTRA_CUSTOMIZATION_MESSAGE = None
    EXTRA_CUSTOMIZATION_DEFAULT = None

    SUPPORTS_SUB_DIRS = False
    MUST_READ_METADATA = False
    SUPPORTS_USE_AUTHOR_SORT = False

    #: If None the default is used
    SAVE_TEMPLATE = None

    @classmethod
    def _default_save_template(cls):
        from calibre.library.save_to_disk import config
        return cls.SAVE_TEMPLATE if cls.SAVE_TEMPLATE else \
            config().parse().send_template

    @classmethod
    def _config_base_name(cls):
        klass = cls if isinstance(cls, type) else cls.__class__
        return klass.__name__

    @classmethod
    def _config(cls):
        name = cls._config_base_name()
        c = Config('device_drivers_%s' % name, _('settings for device drivers'))
        c.add_opt('format_map', default=cls.FORMATS,
                help=_('Ordered list of formats the device will accept'))
        c.add_opt('use_subdirs', default=True,
                help=_('Place files in sub directories if the device supports them'))
        c.add_opt('read_metadata', default=True,
                help=_('Read metadata from files on device'))
        c.add_opt('use_author_sort', default=False,
                help=_('Use author sort instead of author'))
        c.add_opt('save_template', default=cls._default_save_template(),
                help=_('Template to control how books are saved'))
        c.add_opt('extra_customization',
                default=cls.EXTRA_CUSTOMIZATION_DEFAULT,
                help=_('Extra customization'))
        return c

    @classmethod
    def _configProxy(cls):
        return ConfigProxy(cls._config())

    @classmethod
    def config_widget(cls):
        from calibre.gui2.device_drivers.configwidget import ConfigWidget
        cw = ConfigWidget(cls.settings(), cls.FORMATS, cls.SUPPORTS_SUB_DIRS,
            cls.MUST_READ_METADATA, cls.SUPPORTS_USE_AUTHOR_SORT,
            cls.EXTRA_CUSTOMIZATION_MESSAGE)
        return cw

    @classmethod
    def save_settings(cls, config_widget):
        proxy = cls._configProxy()
        proxy['format_map'] = config_widget.format_map()
        if cls.SUPPORTS_SUB_DIRS:
            proxy['use_subdirs'] = config_widget.use_subdirs()
        if not cls.MUST_READ_METADATA:
            proxy['read_metadata'] = config_widget.read_metadata()
        if cls.SUPPORTS_USE_AUTHOR_SORT:
            proxy['use_author_sort'] = config_widget.use_author_sort()
        if cls.EXTRA_CUSTOMIZATION_MESSAGE:
            ec = unicode(config_widget.opt_extra_customization.text()).strip()
            if not ec:
                ec = None
            proxy['extra_customization'] = ec
        st = unicode(config_widget.opt_save_template.text())
        proxy['save_template'] = st

    @classmethod
    def settings(cls):
        return cls._config().parse()

    @classmethod
    def save_template(cls):
        st = cls.settings().save_template
        if st:
            return st
        else:
            return cls._default_save_template()

    @classmethod
    def customization_help(cls, gui=False):
        return cls.HELP_MESSAGE
