"""Turn #hashtags into links to the tag page.

Hashtags are handled as an inline pattern, not a preprocessor. A preprocessor
sees the raw source before fenced code has been set aside, so the previous
version rewrote hashtags inside code blocks: anything containing `#include`
rendered with a literal `<a href="/t/include">` in it. Inline code only
escaped by accident, because a backtick rather than whitespace preceded the #.
Inline patterns run on text nodes after block parsing, and after the backtick
pattern has stashed code spans, so code is never visited.

That move exposes a second problem: Python-Markdown reads "#word" as an <h1>
even without the space CommonMark requires, and the block parser now gets to
it first. On this site "#word" at the start of a line has always been a
tagged paragraph and "# word" a heading, so a small block processor keeps
that distinction by claiming those lines as paragraphs before the heading
processor sees them.
"""

import re
import xml.etree.ElementTree as etree

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor

__author__ = "kongaloosh"

# A tag has to contain a letter or underscore, so "#123" is left alone, but it
# may start with a digit: #3dprinting is a tag here as it is on Mastodon. The
# lookbehind keeps "word#notatag" from matching.
HASHTAG_RE = r"(?:(?<=\s)|^)#(\w*[A-Za-z_]+\w*)"


class HashtagInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        tag = m.group(1)
        link = etree.Element("a")
        link.set("href", f"/t/{tag}")
        link.text = f"#{tag}"
        return link, m.start(0), m.end(0)


class HashtagLineProcessor(BlockProcessor):
    """Claim a block containing a "#word" line as a paragraph, not a heading.

    The heading processor searches the whole block, not just its first line:
    a caption followed by a soft-wrapped line of tags is split, and the tag
    line becomes an <h1>. Roughly sixty posts here are written exactly that
    way, so this has to search too.
    """

    HAS_TAG_LINE = re.compile(r"(?:^|\n)#\w*[A-Za-z_]")

    def test(self, parent, block):
        return bool(self.HAS_TAG_LINE.search(block))

    def run(self, parent, blocks):
        # Hand the block to the real paragraph processor rather than building
        # the element here: it already knows how tight list items differ from
        # top-level paragraphs.
        self.parser.blockprocessors["paragraph"].run(parent, blocks)


class HashtagExtension(Extension):
    def extendMarkdown(self, md):
        # Inline: below the backtick pattern (190), so code spans are already
        # stashed by the time this runs.
        md.inlinePatterns.register(
            HashtagInlineProcessor(HASHTAG_RE, md), "hashtag", 100
        )
        # Block: above hashheader (70) and below indented code (80), so a
        # "#word" line is claimed as a paragraph but indented code is not.
        md.parser.blockprocessors.register(
            HashtagLineProcessor(md.parser), "hashtag_line", 75
        )


def makeExtension(*args, **kwargs):
    return HashtagExtension(*args, **kwargs)
