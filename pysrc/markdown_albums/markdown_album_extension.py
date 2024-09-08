from markdown import Extension
from markdown.preprocessors import Preprocessor
import re

__author__ = 'kongaloosh'

GROUP_WRAP = '''
<div class="album-component d-flex flex-row justify-content-center">
    %s
</div>
'''

IMG_WRAP = \
    '''
    <a class="fancybox p-2 text-center" rel="group"  href="%s">
        <img src="%s" class="u-photo img-responsive img-thumbnail" style="max-height:auto">
    </a>
    '''

album_regexp = r'''(@{3,})(?P<album>((.)|(\n))*?)(@{3,})'''
images_regexp = '(?<=\){1})[ ,\n,\r]*-*[ ,\n,\r]*(?=\[{1})'
image_ref_regexp = '(?<=\({1})(.)*(?=\){1})'
alt_text_regexp = "(?<=\[{1})(.)*(?=\]{1})"


class AlbumExtension(Extension):

    def extendMarkdown(self, md, md_globals):
        """ Add FencedBlockPreprocessor to the Markdown instance. """
        md.registerExtension(self)

        md.preprocessors.add(
            'album',
            AlbumPreprocessor(md),
            ">normalize_whitespace")


class AlbumPreprocessor(Preprocessor):
    ALBUM_GROUP_RE = re.compile(
        album_regexp
    )

    def __init__(self, md):
        super(AlbumPreprocessor, self).__init__(md)

    def run(self, lines):
        """ Match and store Fenced Code Blocks in the HtmlStash."""
        text = "\n".join(
            lines)  # todo: this should totally just be done by going over the lines; not sure what you were thinking
        while True:  # until we are finished parsing the data
            m = self.ALBUM_GROUP_RE.search(text)  # search for an album
            if m:  # if there is a match
                images = re.split(images_regexp, m.group('album'))  # pull out the images
                # todo: could probably just do it once for both and zip into tuple
                generated_html = ""  # where the html is stashed
                for image in images:  # for each image in the album
                    alt = re.search(alt_text_regexp, image).group()  # get the alt text
                    image_location = re.search(image_ref_regexp, image).group()  # get the image reference
                    generated_html += IMG_WRAP % (
                        # todo: images needs to be factored out based on whatever the server is using as the destination
                        "/images" + image_location,     # the location where the images are stored in full-resolution
                        image_location,                 # the location where the image is stored for being served
                        )
                # finally put html album into div
                generated_html = GROUP_WRAP % generated_html  # todo: should add the alt text in
                placeholder = self.markdown.htmlStash.store(generated_html, safe=True)
                text = '%s\n%s\n%s' % (text[:m.start()],  # put everything in the match before the album
                                       placeholder,  # put the new html album
                                       text[m.end():])  # put everything after the album
            else:  # if there are no remaining matches
                break  # stop processing
        return text.split("\n")  # break into lines to return


def make_extension(*args, **kwargs):
    return AlbumExtension(*args, **kwargs)
