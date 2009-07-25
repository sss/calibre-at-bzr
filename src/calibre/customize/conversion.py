# -*- coding: utf-8 -*-
'''
Defines the plugin system for conversions.
'''
import re, os, shutil

from calibre import CurrentDir
from calibre.customize import Plugin

class ConversionOption(object):

    '''
    Class representing conversion options
    '''

    def __init__(self, name=None, help=None, long_switch=None,
                 short_switch=None, choices=None):
        self.name = name
        self.help = help
        self.long_switch = long_switch
        self.short_switch = short_switch
        self.choices = choices

        if self.long_switch is None:
            self.long_switch = self.name.replace('_', '-')

        self.validate_parameters()

    def validate_parameters(self):
        '''
        Validate the parameters passed to :method:`__init__`.
        '''
        if re.match(r'[a-zA-Z_]([a-zA-Z0-9_])*', self.name) is None:
            raise ValueError(self.name + ' is not a valid Python identifier')
        if not self.help:
            raise ValueError('You must set the help text')

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def clone(self):
        return ConversionOption(name=self.name, help=self.help,
                long_switch=self.long_switch, short_switch=self.short_switch,
                choices=self.choices)

class OptionRecommendation(object):
    LOW  = 1
    MED  = 2
    HIGH = 3

    def __init__(self, recommended_value=None, level=LOW, **kwargs):
        '''
        An option recommendation. That is, an option as well as its recommended
        value and the level of the recommendation.
        '''
        self.level = level
        self.recommended_value = recommended_value
        self.option = kwargs.pop('option', None)
        if self.option is None:
            self.option = ConversionOption(**kwargs)

        self.validate_parameters()

    @property
    def help(self):
        return self.option.help

    def clone(self):
        return OptionRecommendation(recommended_value=self.recommended_value,
                level=self.level, option=self.option.clone())

    def validate_parameters(self):
        if self.option.choices and self.recommended_value not in \
                                                    self.option.choices:
            raise ValueError('OpRec: %s: Recommended value not in choices'%
                             self.option.name)
        if not (isinstance(self.recommended_value, (int, float, str, unicode))\
            or self.recommended_value is None):
            raise ValueError('OpRec: %s:'%self.option.name +
                             repr(self.recommended_value) +
                             ' is not a string or a number')

class DummyReporter(object):

    def __call__(self, percent, msg=''):
        pass

class InputFormatPlugin(Plugin):
    '''
    InputFormatPlugins are responsible for converting a document into
    HTML+OPF+CSS+etc.
    The results of the conversion *must* be encoded in UTF-8.
    The main action happens in :method:`convert`.
    '''

    type = _('Conversion Input')
    can_be_disabled = False
    supported_platforms = ['windows', 'osx', 'linux']

    #: Set of file types for which this plugin should be run
    #: For example: ``set(['azw', 'mobi', 'prc'])``
    file_types     = set([])

    #: If True, this input plugin generates a collection of images,
    #: one per HTML file. You can obtain access to the images via
    #: convenience method, :method:`get_image_collection`.
    is_image_collection = False

    #: If set to True, the input plugin will perform special processing
    #: to make its output suitable for viewing
    for_viewer = False

    #: Options shared by all Input format plugins. Do not override
    #: in sub-classes. Use :member:`options` instead. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    common_options = set([
        OptionRecommendation(name='debug_input',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Save the output from the input plugin to the specified '
                   'directory. Useful if you are unsure at which stage '
                   'of the conversion process a bug is occurring. '
                   'WARNING: This completely deletes the contents of '
                   'the specified directory.')
        ),

        OptionRecommendation(name='input_encoding',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the input document. If '
                   'set this option will override any encoding declared by the '
                   'document itself. Particularly useful for documents that '
                   'do not declare an encoding or that have erroneous '
                   'encoding declarations.')
        ),

    ])

    #: Options to customize the behavior of this plugin. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    options = set([])

    #: A set of 3-tuples of the form
    #: (option_name, recommended_value, recommendation_level)
    recommendations = set([])

    def __init__(self, *args):
        Plugin.__init__(self, *args)
        self.report_progress = DummyReporter()

    def get_images(self):
        '''
        Return a list of absolute paths to the images, if this input plugin
        represents an image collection. The list of images is in the same order
        as the spine and the TOC.
        '''
        raise NotImplementedError()

    def preprocess_html(self, html):
        '''
        This method is called by the conversion pipeline on all HTML before it
        is parsed. It is meant to be used to do any required preprocessing on
        the HTML, like removing hard line breaks, etc.

        :param html: A unicode string
        :return: A unicode string
        '''
        return html


    def convert(self, stream, options, file_ext, log, accelerators):
        '''
        This method must be implemented in sub-classes. It must return
        the path to the created OPF file or an :class:`OEBBook` instance.
        All output should be contained in the current directory.
        If this plugin creates files outside the current
        directory they must be deleted/marked for deletion before this method
        returns.

        :param stream:   A file like object that contains the input file.

        :param options:  Options to customize the conversion process.
                         Guaranteed to have attributes corresponding
                         to all the options declared by this plugin. In
                         addition, it will have a verbose attribute that
                         takes integral values from zero upwards. Higher numbers
                         mean be more verbose. Another useful attribute is
                         ``input_profile`` that is an instance of
                         :class:`calibre.customize.profiles.InputProfile`.

        :param file_ext: The extension (without the .) of the input file. It
                         is guaranteed to be one of the `file_types` supported
                         by this plugin.

        :param log: A :class:`calibre.utils.logging.Log` object. All output
                    should use this object.

        :param accelarators: A dictionary of various information that the input
                             plugin can get easily that would speed up the
                             subsequent stages of the conversion.

        '''
        raise NotImplementedError

    def __call__(self, stream, options, file_ext, log,
                 accelerators, output_dir):
        log('InputFormatPlugin: %s running'%self.name, end=' ')
        if hasattr(stream, 'name'):
            log('on', stream.name)

        with CurrentDir(output_dir):
            for x in os.listdir('.'):
                shutil.rmtree(x) if os.path.isdir(x) else os.remove(x)

            ret = self.convert(stream, options, file_ext,
                               log, accelerators)

        if options.debug_input is not None:
            options.debug_input = os.path.abspath(options.debug_input)
            if not os.path.exists(options.debug_input):
                os.makedirs(options.debug_input)
            if isinstance(ret, basestring):
                shutil.rmtree(options.debug_input)
                shutil.copytree(output_dir, options.debug_input)
            else:
                from calibre.ebooks.oeb.writer import OEBWriter
                w = OEBWriter(pretty_print=options.pretty_print)
                w(ret, options.debug_input)

            log.info('Input debug saved to:', options.debug_input)

        return ret

    def postprocess_book(self, oeb, opts, log):
        pass

class OutputFormatPlugin(Plugin):
    '''
    OutputFormatPlugins are responsible for converting an OEB document
    (OPF+HTML) into an output ebook.

    The OEB document can be assumed to be encoded in UTF-8.
    The main action happens in :method:`convert`.
    '''

    type = _('Conversion Output')
    can_be_disabled = False
    supported_platforms = ['windows', 'osx', 'linux']

    #: The file type (extension without leading period) that this
    #: plugin outputs
    file_type     = None

    #: Options shared by all Input format plugins. Do not override
    #: in sub-classes. Use :member:`options` instead. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    common_options = set([
        OptionRecommendation(name='pretty_print',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('If specified, the output plugin will try to create output '
            'that is as human readable as possible. May not have any effect '
            'for some output plugins.')
        ),
        ])

    #: Options to customize the behavior of this plugin. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    options = set([])

    #: A set of 3-tuples of the form
    #: (option_name, recommended_value, recommendation_level)
    recommendations = set([])

    def __init__(self, *args):
        Plugin.__init__(self, *args)
        self.report_progress = DummyReporter()


    def convert(self, oeb_book, output, input_plugin, opts, log):
        '''
        Render the contents of `oeb_book` (which is an instance of
        :class:`calibre.ebooks.oeb.OEBBook` to the file specified by output.

        :param output: Either a file like object or a string. If it is a string
        it is the path to a directory that may or may not exist. The output
        plugin should write its output into that directory. If it is a file like
        object, the output plugin should write its output into the file.

        :param input_plugin: The input plugin that was used at the beginning of
        the conversion pipeline.

        :param opts: Conversion options. Guaranteed to have attributes
        corresponding to the OptionRecommendations of this plugin.

        :param log: The logger. Print debug/info messages etc. using this.
        '''
        raise NotImplementedError

