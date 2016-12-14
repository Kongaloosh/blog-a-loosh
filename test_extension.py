import markdown
from pysrc.file_management.markdown_album_extension import AlbumExtension
from pysrc.file_management.markdown_hashtag_extension import HashtagExtension
__author__ = 'kongaloosh'


if __name__ == "__main__":
    # str = """#here"""
    # print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])
    #
    # str = "here #there"
    # print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])
    #
    # str = """#here there"""
    # print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])

    str = \
    """
    here

    #sadiofjs asdiojijs
    #herethere taoisdhf #asdifjosidjf sdifoij
    saoifjsdoi
    """
    print(str)
    print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])