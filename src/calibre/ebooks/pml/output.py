# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

try:
    from PIL import Image
    Image
except ImportError:
    import Image

import cStringIO

from calibre.customize.conversion import OutputFormatPlugin
from calibre.customize.conversion import OptionRecommendation
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES
from calibre.ebooks.pml.pmlml import PMLMLizer

class PMLOutput(OutputFormatPlugin):

    name = 'PML Output'
    author = 'John Schember'
    file_type = 'pmlz'

    options = set([
        OptionRecommendation(name='output_encoding', recommended_value='cp1252',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. ' \
            'The default is cp1252.')),
        OptionRecommendation(name='inline_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Add Table of Contents to beginning of the book.')),
        OptionRecommendation(name='full_image_depth',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Do not reduce the size or bit depth of images. Images ' \
                   'have their size and depth reduced by default to accommodate ' \
                   'applications that can not convert images on their ' \
                   'own such as Dropbook.')),
    ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        with TemporaryDirectory('_pmlz_output') as tdir:
            pmlmlizer = PMLMLizer(log)
            pml = unicode(pmlmlizer.extract_content(oeb_book, opts))
            with open(os.path.join(tdir, 'index.pml'), 'wb') as out:
                out.write(pml.encode(opts.output_encoding, 'replace'))

            self.write_images(oeb_book.manifest, pmlmlizer.image_hrefs, tdir, opts)

            log.debug('Compressing output...')
            pmlz = ZipFile(output_path, 'w')
            pmlz.add_dir(tdir)

    def write_images(self, manifest, image_hrefs, out_dir, opts):
        for item in manifest:
            if item.media_type in OEB_RASTER_IMAGES and item.href in image_hrefs.keys():
                if opts.full_image_depth:
                    im = Image.open(cStringIO.StringIO(item.data))
                else:
                    im = Image.open(cStringIO.StringIO(item.data)).convert('P')
                    im.thumbnail((300,300), Image.ANTIALIAS)

                data = cStringIO.StringIO()
                im.save(data, 'PNG')
                data = data.getvalue()

                path = os.path.join(out_dir, image_hrefs[item.href])

                with open(path, 'wb') as out:
                    out.write(data)
