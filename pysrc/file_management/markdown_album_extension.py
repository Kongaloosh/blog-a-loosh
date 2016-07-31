__author__ = 'kongaloosh'
from markdown import Extension
from markdown.preprocessors import Preprocessor
import re


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
        r'''(@{3,})(?P<album>((.)|(\n))*?)(@{3,})'''
    )

    GROUP_WRAP = '''
    <div class="album-component row text-center">
        %s
    </div>
    '''
    IMG_WRAP = \
        '''
        <a class="fancybox" rel="group"  href="%s">
            <img src="%s" class="img-responsive img-thumbnail" style="width:%d%%">
        </a>
        '''

    def __init__(self, md):
        super(AlbumPreprocessor, self).__init__(md)

    def run(self, lines):
        """ Match and store Fenced Code Blocks in the HtmlStash. """

        text = "\n".join(lines)
        while 1:
            m = self.ALBUM_GROUP_RE.search(text)
            if m:                                    # if there is a match

                album_collection = ""

                images = re.split("(?<=\){1})[ ,\n]*-*[ ,\n]*(?=\[{1})", m.group('album'))
                # could probably just do it once for both and zip into tuple
                generated_html = ""
                for image in images:                    # for each image in the album
                    alt = re.search("(?<=\[{1})(.)*(?=\]{1})",image).group() # get the alt text
                    image_location = re.search("(?<=\({1})(.)*(?=\){1})",image).group()
                    generated_html += self.IMG_WRAP % (image_location, image_location, 100/(len(images)+.2))

                # finally put code into div
                generated_html = self.GROUP_WRAP % (generated_html)

                placeholder = self.markdown.htmlStash.store(generated_html, safe=True)
                text = '%s\n%s\n%s' % (text[:m.start()],
                                       placeholder,
                                       text[m.end():])
            else:
                break
        return text.split("\n")


def makeExtension(*args, **kwargs):
    return AlbumExtension(*args, **kwargs)

