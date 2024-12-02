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
        """Process hashtags and convert them to links."""
        new_lines = []
        for line in lines:
            while True:
                m = self.ALBUM_GROUP_RE.search(line)
                if m:
                    tag = m.group(1)
                    link = f'<a href="/t/{tag}">#{tag}</a>'
                    line = line[: m.start()] + link + line[m.end() :]
                else:
                    break
            new_lines.append(line)
        return new_lines


def makeExtension(*args, **kwargs):
    return HashtagExtension(*args, **kwargs)
