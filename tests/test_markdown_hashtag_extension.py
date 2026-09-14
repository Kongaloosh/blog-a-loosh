import pytest
from markdown import Markdown
from pysrc.markdown_hashtags.markdown_hashtag_extension import HashtagExtension


@pytest.fixture
def md():
    """A Markdown instance configured the way the app configures it.

    The app loads "extra" alongside the hashtag extension (kongaloosh.py),
    which is what provides fenced code blocks; without it the fenced-code
    test exercises a renderer the site never uses.
    """
    return Markdown(extensions=["extra", HashtagExtension()])


def test_basic_hashtag(md):
    """Test basic hashtag conversion"""
    text = "This is a #test"
    expected = '<p>This is a <a href="/t/test">#test</a></p>'
    assert md.convert(text) == expected


def test_multiple_hashtags(md):
    """Test multiple hashtags in one line"""
    text = "This #post has #multiple hashtags"
    expected = '<p>This <a href="/t/post">#post</a> has <a href="/t/multiple">#multiple</a> hashtags</p>'
    assert md.convert(text) == expected


def test_hashtag_with_underscore(md):
    """Test hashtags containing underscores"""
    text = "This is a #long_hashtag"
    expected = '<p>This is a <a href="/t/long_hashtag">#long_hashtag</a></p>'
    assert md.convert(text) == expected


def test_hashtag_at_start(md):
    """Test hashtag at start of line"""
    text = "#start of line"
    expected = '<p><a href="/t/start">#start</a> of line</p>'
    assert md.convert(text) == expected


def test_hashtag_at_end(md):
    """Test hashtag at end of line"""
    text = "end of line #end"
    expected = '<p>end of line <a href="/t/end">#end</a></p>'
    assert md.convert(text) == expected


def test_invalid_hashtags(md):
    """Test invalid hashtag patterns that shouldn't match"""
    invalid_cases = [
        ("This #123 shouldn't match", "<p>This #123 shouldn't match</p>"),
        ("This # shouldn't match", "<p>This # shouldn't match</p>"),
        ("This #!invalid shouldn't match", "<p>This #!invalid shouldn't match</p>"),
        (
            "This#not_a_hashtag shouldn't match",
            "<p>This#not_a_hashtag shouldn't match</p>",
        ),
    ]
    for text, expected in invalid_cases:
        assert md.convert(text) == expected


def test_hashtag_in_code_block(md):
    """Test hashtags in code blocks should not be converted"""
    text = "```\nThis #code should not be converted\n```"
    expected = "<pre><code>This #code should not be converted\n</code></pre>"
    assert md.convert(text) == expected


def test_hashtag_in_inline_code(md):
    """Test hashtags in inline code should not be converted"""
    text = "This `#code` should not be converted"
    expected = "<p>This <code>#code</code> should not be converted</p>"
    assert md.convert(text) == expected


def test_hashtag_with_punctuation(md):
    """Test hashtags followed by punctuation"""
    cases = [
        ("This #tag.", '<p>This <a href="/t/tag">#tag</a>.</p>'),
        ("This #tag!", '<p>This <a href="/t/tag">#tag</a>!</p>'),
        ("This #tag?", '<p>This <a href="/t/tag">#tag</a>?</p>'),
        ("This #tag,", '<p>This <a href="/t/tag">#tag</a>,</p>'),
    ]
    for text, expected in cases:
        assert md.convert(text) == expected


def test_hashtag_in_list(md):
    """Test hashtags in markdown lists"""
    text = """
- Item with #tag1
- Another item with #tag2
"""
    expected = '<ul>\n<li>Item with <a href="/t/tag1">#tag1</a></li>\n<li>Another item with <a href="/t/tag2">#tag2</a></li>\n</ul>'
    assert md.convert(text.strip()) == expected


def test_hashtag_in_blockquote(md):
    """Test hashtags in blockquotes"""
    text = "> This is a quote with #tag"
    expected = '<blockquote>\n<p>This is a quote with <a href="/t/tag">#tag</a></p>\n</blockquote>'
    assert md.convert(text) == expected


def test_multiple_hashtags_same_word(md):
    """Test multiple hashtags of the same word"""
    text = "This #tag appears twice as #tag"
    expected = '<p>This <a href="/t/tag">#tag</a> appears twice as <a href="/t/tag">#tag</a></p>'
    assert md.convert(text) == expected


def test_hashtag_case_sensitivity(md):
    """Test hashtag case sensitivity"""
    text = "Compare #Tag with #tag"
    expected = '<p>Compare <a href="/t/Tag">#Tag</a> with <a href="/t/tag">#tag</a></p>'
    assert md.convert(text) == expected


def test_hashtag_with_numbers(md):
    """A tag may contain digits anywhere, including the start.

    The only rule is that it must contain a letter, which keeps a bare
    "#123" from matching (see test_invalid_hashtags). #3dprinting and
    #1password are tags on every platform this site syndicates to.
    """
    text = "Both: #tag123 and #123tag"
    expected = (
        '<p>Both: <a href="/t/tag123">#tag123</a>'
        ' and <a href="/t/123tag">#123tag</a></p>'
    )
    assert md.convert(text) == expected


def test_hashtag_after_space_inside_inline_code(md):
    """Inline code is untouched even when whitespace precedes the #.

    Regression: the preprocessor version only spared `#code` because a
    backtick, not a space, came before the #; this form was rewritten.
    """
    text = "Run `make #all` now"
    expected = "<p>Run <code>make #all</code> now</p>"
    assert md.convert(text) == expected


def test_hashtag_in_indented_code_block(md):
    """Indented code blocks are untouched too, not just fenced ones."""
    text = "    #include <stdio.h>"
    expected = "<pre><code>#include &lt;stdio.h&gt;\n</code></pre>"
    assert md.convert(text) == expected


def test_reset_between_conversions(md):
    """Test that the extension properly resets between conversions"""
    text1 = "This is #test1"
    text2 = "This is #test2"

    result1 = md.convert(text1)
    result2 = md.convert(text2)

    assert '<a href="/t/test1">#test1</a>' in result1
    assert '<a href="/t/test2">#test2</a>' in result2


def test_heading_with_space_is_still_a_heading(md):
    """"# word" is a heading; only "#word" is a tag. Keep the distinction."""
    assert md.convert("# Real heading") == "<h1>Real heading</h1>"
    assert md.convert("## Sub heading") == "<h2>Sub heading</h2>"


def test_hashtag_starting_a_list_item(md):
    """A tag opening a tight list item must not get wrapped in <p>."""
    text = "- #first item\n- second"
    expected = (
        '<ul>\n<li><a href="/t/first">#first</a> item</li>\n<li>second</li>\n</ul>'
    )
    assert md.convert(text) == expected


def test_tag_line_soft_wrapped_inside_a_paragraph(md):
    """Regression: a tag line following a caption in the same block became
    an <h1>, because the heading processor searches the whole block."""
    text = "More holiday parties\n#cat #catsofinstagram"
    expected = (
        '<p>More holiday parties\n<a href="/t/cat">#cat</a>'
        ' <a href="/t/catsofinstagram">#catsofinstagram</a></p>'
    )
    assert md.convert(text) == expected
