import pytest
from markdown import Markdown
from pysrc.markdown_hashtags.markdown_hashtag_extension import HashtagExtension


@pytest.fixture
def md():
    """Create a Markdown instance with HashtagExtension"""
    return Markdown(extensions=[HashtagExtension()])


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
    """Test hashtags containing numbers (but not starting with them)"""
    text = "Valid: #tag123 Invalid: #123tag"
    expected = '<p>Valid: <a href="/t/tag123">#tag123</a> Invalid: #123tag</p>'
    assert md.convert(text) == expected


def test_reset_between_conversions(md):
    """Test that the extension properly resets between conversions"""
    text1 = "This is #test1"
    text2 = "This is #test2"

    result1 = md.convert(text1)
    result2 = md.convert(text2)

    assert '<a href="/t/test1">#test1</a>' in result1
    assert '<a href="/t/test2">#test2</a>' in result2
