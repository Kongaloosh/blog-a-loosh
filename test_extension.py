import markdown
from pysrc.file_management.markdown_album_extension import AlbumExtension
from pysrc.file_management.markdown_hashtag_extension import HashtagExtension
__author__ = 'kongaloosh'


if __name__ == "__main__":
    str = """#here"""
    print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])