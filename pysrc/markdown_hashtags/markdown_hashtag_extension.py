from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
import re

__author__ = "kongaloosh"


class HashtagExtension(Extension):

    def extendMarkdown(self, md):
        """Add FencedBlockPreprocessor to the Markdown instance."""
        md.preprocessors.register(HashtagPreprocessor(md), "hashtag", 175)


class HashtagPreprocessor(Preprocessor):
    ALBUM_GROUP_RE = re.compile(r"""(?:(?<=\s)|^)#(\w*[A-Za-z_]+\w*)""")

    def run(self, lines):
        """Match and store Fenced Code Blocks in the HtmlStash."""
        HASHTAG_WRAP = """<a href="/t/{0}"> #{0}</a>"""
        text = "\n".join(lines)
        while True:
            hashtag = ""
            m = self.ALBUM_GROUP_RE.search(text)
            if m:  # if there is a match
                hashtag += HASHTAG_WRAP.format(m.group()[1:])
                placeholder = self.md.htmlStash.store(hashtag)
                text = "%s %s %s" % (text[: m.start()], placeholder, text[m.end() :])
            else:
                break
        return text.split("\n")


def makeExtension(*args, **kwargs):
    return HashtagExtension(*args, **kwargs)
