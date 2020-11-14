# import markdown
# # mport shutil, tempfile
# import os
# from pysrc.file_management.markdown_album_extension import AlbumExtension
# import pysrc.file_management.markdown_album_pre_process as album
# from pysrc.file_management.markdown_hashtag_extension import HashtagExtension
# import unittest
#
# __author__ = 'kongaloosh'
#
# # class AlbumExtensionPreProcessTest(unittest.TestCase):
# #
# #     def setUp(self):
# #         # Create a temporary directory
# #
# #
# #     def tearDown(self):
# #         # Remove the directory after the test
# #         os.rmdir(album.old_prefix)          # remove the /temp/
# #         os.rmdir(album.new_prefix)          # remove the /photo/
#
#
# if __name__ == "__main__":
#     # str = """#here"""
#     # print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])
#     #
#     # str = "here #there"
#     # print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])
#     #
#     # str = """#here there"""
#     # print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])
#
#     str = \
#     """
#     here
#
#     #sadiofjs asdiojijs
#     #herethere taoisdhf #asdifjosidjf sdifoij
#     saoifjsdoi
#     """
#
#     print markdown.markdown(str, extensions=[AlbumExtension(), HashtagExtension()])
#     album.old_prefix = "test_data/"
#     album.new_prefix = "test_data/"
#
#
#     print album.run(""""
# @@@[](/images/temp/1.JPG)@@@
#
# @@@[](/images/temp/2.JPG)-[](/images/temp/3.JPG)-[](/images/temp/4.JPG)@@@
#
# @@@[](/images/temp/5.JPG)-[](/images/temp/6.JPG)@@@
#
# """)
#
# print album.run("""I flew down to Wyoming on the weekend to go see the Solar Eclipse. This was a spur of the moment trip; a family friend is an amateur astronomer and was planning on driving down on the weekend to be able to catch the eclipse.
#
# One problem with their plan: motel rooms within driving distance of the totality were going for $1200 or more on the evening before the eclipse.
#
# One solution: motel rooms within flying distance of the totality were going for 90$ a night the evening before the eclipse.
#
#
#
# @@@[](/data/2017/8/25/img_6838.jpg)-[](/data/2017/8/25/img_6834.jpg)-[](/data/2017/8/25/img_6837.jpg)@@@
#
#
#
# Instead of driving down, we all flew down from Calgary, stayed the night in Montana, and on the morning of the eclipse flew in to [Riverton, Wyoming](https://en.wikipedia.org/wiki/Riverton,_Wyoming), a town of roughly 11,000 people.
#
# Why the fuss of trying to get onto the totality line? In many places you could see the sun turn into a sliver during the eclipse, but only if you had the protective eyewear. In a few places stretching across the east to west of the U.S. you were able to see the eclipse in it's totality; for just over two minutes the sun would be entirely blocked by the moon, allowing you to see the sun's corona.
#
# ### A Surreal Setting
#
# They really pulled out all the stops in Riverton for the eclipse. There were a couple of people with walkie-talkies and an ATV set up as temporary ground-control. On arrival they pointed you towards a breakfast barbecue they'd setup for all the planes which flew in for the day.
#
# Apparently we weren't the only people to come up with this plan.
#
#
#
# @@@[](/data/2017/8/25/img_7309.jpg)-[](/data/2017/8/25/img_7302.jpg)@@@
#
#
#
# One of the most interesting aspects was the sheer number of planes. There were a score of private jets on the ramp, including a challenger, and probably close to a hundred small personal planes on the tarmac and grass surrounding the airstrip. A few people were camping next to their planes overnight. A number of the private jets erected shelters and had party games under their wings.
#
# It was like a tailgate party for plane people.
#
# 11,000 people live in this town and it suddenly had hundreds of millions of dollars in planes sitting on the tarmac, only to leave when the eclipse was over.
#
# ### The Most Impressive Sight I've Seen
#
# To view the eclipse we brought a number of welders glasses which we could layer depending on the cloud-cover and intensity of the sunlight. At first you could only see a little dimple in the top of the sun. As the dimple grew and the moon covered more of the sun, it got dimmer and dimmer, but not fast enough that you noticed it immediately. Even when mostly covered, the sun never really seemed like it was covered.
#
#
#
# @@@
# [](/data/2017/8/25/img_6859.jpg)
# @@@
#
#
#
# There was this dissonance: the sun was bright and it felt like noon, but everything had a strange tint. It was like someone had turned the contrast up on life. Shadows got sharper. The temperature dropped and eventually I got a chill even though it had been a balmy summer day.
#
#
#
# @@@[](/data/2017/8/25/img_6863.jpg)-[](/data/2017/8/25/img_7321.jpg)@@@
#
#
#
# Then the totality started.
#
#
#
# @@@
# [](/data/2017/8/25/totality_2stars at l. at noon.jpg)
# @@@
#
#
#
# All of a sudden the sun blinked out, covered by the moon. Around the eclipse you could see the corona of the sun---an aura of plasma surrounding the sun. There were jets pointing out from around the sun where you could see.
#
# There was a pink and purple sunset on every horizon. If you looked close enough around the sun, you could see a number of planets including Mercury and Venus. Being able to see mercury was a treat, as it's usually challenging to see with the naked eye.
#
# It was awe-inspiring .
#
#
#
# @@@
# [](/data/2017/8/25/jfs_1918a.jpg)
# @@@
#
#
#
# When the totality came to an end, it was like there were sparkles erupting from the sun's corona. The moon has a number of craters in its side---craters which will allow some streaks of light through before the moon only partial eclipses the sun. This creates a bubbling and twinkling that only lasts a couple of seconds before the sun returns to a shining partial-eclipse.
#
#
#
# @@@
# [](/data/2017/8/25/img_6845.jpg)
# @@@
#
#
#
# We were really fortunate that the weather coming down and the weather on the day of the eclipse was in our favour. The cloud-cover parted just before the totality, giving us the perfect opportunity to see an astronomical event we may not have the chance to see again. """)