from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
import re
import configparser
import os
import posixpath

__author__ = "kongaloosh"

GROUP_WRAP = """
<div class="album-component d-flex flex-row justify-content-center">
    %s
</div>
"""

IMG_WRAP = """
    <a class="fancybox p-2 text-center" rel="group"  href="%s">
        <img src="%s" class="u-photo img-responsive img-thumbnail" style="max-height:auto">
    </a>
    """

album_regexp = r"""(@{3,})(?P<album>((.)|(\n))*?)(@{3,})"""
images_regexp = "(?<=\){1})[ ,\n,\r]*-*[ ,\n,\r]*(?=\[{1})"
image_ref_regexp = "(?<=\({1})(.)*(?=\){1})"
alt_text_regexp = "(?<=\[{1})(.)*(?=\]{1})"

# Load config
config = configparser.ConfigParser()
config.read("config.ini")
BULK_UPLOAD_DIR = config["PhotoLocations"]["BulkUploadLocation"]
PERMANENT_PHOTOS_DIR = config["PhotoLocations"]["PermStorage"]
BLOG_STORAGE = config["PhotoLocations"]["BlogStorage"]


class AlbumExtension(Extension):

    def extendMarkdown(self, md):
        """Add FencedBlockPreprocessor to the Markdown instance."""
        album_preprocessor = AlbumPreprocessor(md)
        md.preprocessors.register(album_preprocessor, "album", 175)


class AlbumPreprocessor(Preprocessor):
    ALBUM_GROUP_RE = re.compile(album_regexp)

    def __init__(self, md):
        super().__init__(md)
        self.markdown = md

    def run(self, lines):
        """Match and store Fenced Code Blocks in the HtmlStash."""
        text = "\n".join(lines)
        while True:
            m = self.ALBUM_GROUP_RE.search(text)
            if m:
                images = re.split(images_regexp, m.group("album"))
                generated_html = ""
                for image in images:
                    try:
                        alt = re.search(alt_text_regexp, image).group()
                        image_location = re.search(image_ref_regexp, image).group()

                        # Strip any leading slash for consistent joining
                        image_location = image_location.lstrip("/")

                        if image_location.startswith(BULK_UPLOAD_DIR):
                            path = posixpath.join("/", image_location)
                            href_path = path
                            src_path = path
                        else:
                            base_path = image_location.removeprefix(BLOG_STORAGE)
                            base_path = base_path.lstrip("/")
                            src_path = posixpath.join("/", image_location)
                            href_path = posixpath.join(
                                "/", PERMANENT_PHOTOS_DIR, base_path
                            )
                        generated_html += IMG_WRAP % (href_path, src_path)
                    except Exception as e:
                        print(f"Error processing image {image}: {e}")
                generated_html = GROUP_WRAP % generated_html
                text = "%s\n%s\n%s" % (
                    text[: m.start()],
                    generated_html,
                    text[m.end() :],
                )
            else:
                break
        return text.split("\n")


def make_extension(*args, **kwargs):
    return AlbumExtension(*args, **kwargs)
