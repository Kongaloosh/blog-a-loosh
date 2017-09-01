import markdown
# mport shutil, tempfile
import os
from pysrc.file_management.markdown_album_extension import AlbumExtension
import pysrc.file_management.markdown_album_pre_process as album
from pysrc.file_management.markdown_hashtag_extension import HashtagExtension
import unittest

__author__ = 'kongaloosh'

# class AlbumExtensionPreProcessTest(unittest.TestCase):
#
#     def setUp(self):
#         # Create a temporary directory
#
#
#     def tearDown(self):
#         # Remove the directory after the test
#         os.rmdir(album.old_prefix)          # remove the /temp/
#         os.rmdir(album.new_prefix)          # remove the /photo/


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

    print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])
    album.old_prefix = "test_data/"
    album.new_prefix = "test_data/"


    print album.run(""""
@@@[](/images/temp/1.JPG)@@@

@@@[](/images/temp/2.JPG)-[](/images/temp/3.JPG)-[](/images/temp/4.JPG)@@@

@@@[](/images/temp/5.JPG)-[](/images/temp/6.JPG)@@@

""")
