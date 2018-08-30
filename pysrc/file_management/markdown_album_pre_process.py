__author__ = 'kongaloosh'

from markdown import Extension
from markdown.preprocessors import Preprocessor
import re
from PIL import Image
from datetime import datetime
import os

old_prefix = '/home/deploy/kongaloosh/'
new_prefix = '/mnt/volume-nyc1-01/'

# the regular expression to find albums
ALBUM_GROUP_RE = re.compile(
    r'''(@{3,})(?P<album>((.)|(\n))*?)(@{3,})'''
)

def move(loc, date):
    """"
    Moves an image, scales it and stores a low-res with the blog post and a high-res in a long-term storage folder.
    :param loc: the location of an image
    :param loc: the date folder to which an image should be moved
    """
    if date is None:
        date = datetime.now()

    date_suffix = "data/{0}/{1}/{2}/".format(
        date.year,
        date.month,
        date.day
    )

    file_name = loc[13:]                                                    # remove the '/images/temp/'
    target_file_path = new_prefix + loc[1:]
    if not os.path.exists(new_prefix+'images/' + date_suffix):              # if the target directory doesn't exist ...
        print new_prefix
        os.makedirs(os.path.dirname(new_prefix+'images/'+date_suffix))      # ... make it.
    img = Image.open(target_file_path)                                      # open the image from the temp
    img.save(new_prefix+'images/'+date_suffix+file_name.lower())            # open the new location

    max_height = 500                                            # maximum height
    img = Image.open(target_file_path)                          # open the image in PIL
    h_percent = (max_height / float(img.size[1]))               # calculate what percentage the new height is of the old
    w_size = int((float(img.size[0]) * float(h_percent)))       # calculate the new size of the width
    img = img.resize((w_size, max_height), Image.ANTIALIAS)     # translate the image
    try:
        if not os.path.exists(old_prefix+date_suffix):              # if the blog's directory doesn't exist
            os.makedirs(os.path.dirname(old_prefix+date_suffix))    # make it
        img.save(old_prefix+date_suffix+file_name.lower())          # image save old_prefix
    except OSError:
        pass
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory
    os.remove(target_file_path)
    return "/" + date_suffix+file_name.lower()                          # of form data/yyyy/mm/dd/name.extension


def run(lines, date=None):
    """
    Finds all references to images, removes them from their temporary directory, moves them to their new location, 
    and replaces references to them in the original post text.
    :param lines: the text of an entry which may, or may or may not have photos.
    :param date: the date this post was made.
    """

    # 1. find all the references to images
    text = lines
    last_index = -1
    finished = False
    while not finished:
        # given the substitution, the new entries will likely be longer
        # ie. images/temp/name.jpg is shorter than data/yyyy/mm/dd/name
        # substituting immediately in will cause overlap
        # we need this loop to go over iteratively; we keep track of where we were last with
        collections = ALBUM_GROUP_RE.finditer(text)
        if collections:                                             # if there's an image match
            current_index = 0
            while True:
                try:
                    collection = collections.next()
                    current_index += 1
                    if current_index > last_index:
                        # split a daisy chain of images in an album
                        images = re.split(  # split the collection into images
                            "(?<=\){1})[ ,\n]*-*[ ,\n]*(?=\[{1})",
                            collection.group('album')
                        )
                        print images
                        album = ""                                      # where we place reformatted images
                        for index in range(len(images)):                # for image in the whole collection
                            last_index = current_index                  # update

                            image_ref = re.search(
                                "(?<=\({1})(.)*(?=\){1})",
                                images[index]) \
                                .group()                                # get the image location

                            alt = re.search(
                                "(?<=\[{1})(.)*(?=\]{1})",
                                images[index]
                            ).group()                                   # get the text

                            if image_ref.startswith("/images/temp/"):   # if the location is in our temp folder...
                                image_ref = move(image_ref, date)       # ... move and resize photos
                            album += "[%s](%s)" % (alt, image_ref)      # album
                            if index != len(images) - 1:                # if this isn't the last image in the set...
                                album += "-\n"                          # ... then make room for another image

                        current_index = last_index

                        if album is not "":                             # if the album isn't empty
                            text = '%s\n@@@\n%s\n@@@\n%s' % (text[:collection.start()],  # sub it into where the old images were
                                                   album,
                                                   text[collection.end():])
                        last_index = current_index
                        break
                except StopIteration:
                    if current_index == last_index or last_index == -1:
                        finished = True
                    break
        else:
            finished = True
            break
    return text

if __name__ == "__main__":
    lines = """
    @@@[](/images/temp/IMG_6813.JPG)@@@

coffee

@@@
[](/images/temp/IMG_6774.JPG)
@@@

@@@
[](/images/temp/IMG_6828.JPG)
@@@

@@@
[](/images/temp/IMG_6840.JPG)
@@@

@@@
[](/images/temp/IMG_6770.JPG)
@@@

@@@
[](/images/temp/IMG_6802.JPG)-
@@@

Robot shop

@@@
[](/images/temp/IMG_6768.JPG)-
[](/images/temp/IMG_6806.JPG)-
[](/images/temp/IMG_6820.JPG)
@@@

@@@
[](/images/temp/IMG_6778.JPG)-
[](/images/temp/IMG_6805.JPG)-
[](/images/temp/IMG_6797.JPG)-
[](/images/temp/IMG_6819.JPG)
@@@

@@@
[](/images/temp/IMG_6816.JPG)-
[](/images/temp/IMG_6782.JPG)-
[](/images/temp/IMG_6837.JPG)
@@@

@@@
[](/images/temp/IMG_6767.JPG)-
[](/images/temp/IMG_6794.JPG)-
[](/something else/temp/IMG_6801.JPG)
@@@


@@@
[](/images/temp/IMG_6808.JPG)
@@@
"""

    lines = """
        I flew down to Wyoming on the weekend to go see the Solar Eclipse. This was a spur of the moment trip; a family friend is an amateur astronomer and was planning on driving down on the weekend to be able to catch the eclipse. One problem with their plan: motel rooms within driving distance of the totality were going for $1200 or more on the evening before the eclipse. One solution: motel rooms within flying distance of the totality were going for 90$ a night the evening before the eclipse. 

        @@@[](/data/2017/8/25/img_6838.jpg)-[](/data/2017/8/25/img_6834.jpg)-[](/data/2017/8/25/img_6837.jpg)@@@

        Instead of driving down, we all flew down from Calgary, stayed the night in Montana, and on the morning of the eclipse flew in to [Riverton, Wyoming](https://en.wikipedia.org/wiki/Riverton,_Wyoming), a town of roughly 11,000 people. 

Why the fuss of trying to get onto the totality line? In many places you could see the sun turn into a sliver during the eclipse, but only if you had the protective eyewear. In a few places stretching across the east to west of the U.S. you were able to see the eclipse in it's totality; for just over two minutes the sun would be entirely blocked by the moon, allowing you to see the sun's corona.

### A Surreal Setting

They really pulled out all the stops in Riverton for the eclipse. There were a couple of people with walkie-talkies and an ATV set up as temporary ground-control. On arrival they pointed you towards a breakfast barbecue they'd setup for all the planes which flew in for the day. 

Apparently we weren't the only people to come up with this plan.



@@@[](/data/2017/8/25/img_7309.jpg)-[](/data/2017/8/25/img_7302.jpg)@@@



One of the most interesting aspects was the sheer number of planes. There were a score of private jets on the ramp, including a challenger, and probably close to a hundred small personal planes on the tarmac and grass surrounding the airstrip. A few people were camping next to their planes overnight. A number of the private jets erected shelters and had party games under their wings. 

It was like a tailgate party for plane people. 

11,000 people live in this town and it suddenly had hundreds of millions of dollars in planes sitting on the tarmac, only to leave when the eclipse was over.

### The Most Impressive Sight I've Seen

To view the eclipse we brought a number of welders glasses which we could layer depending on the cloud-cover and intensity of the sunlight. At first you could only see a little dimple in the top of the sun. As the dimple grew and the moon covered more of the sun, it got dimmer and dimmer, but not fast enough that you noticed it immediately. Even when mostly covered, the sun never really seemed like it was covered. 



@@@
[](/data/2017/8/25/img_6859.jpg)
@@@



    
    """
    print run(lines, date=None)
