__author__ = 'kongaloosh'
from markdown import Extension
from markdown.preprocessors import Preprocessor
import re
from PIL import Image
from datetime import datetime
import os

def move(loc, date):
    # open old file
    # you're going to need to check trailing slashes
    old_prefix = '/home/deploy/kongaloosh/'
    new_prefix = '/mnt/volume-nyc1-01/'

    if date is None:
        date = datetime.now()

    date_suffix = "data/{0}/{1}/{2}/".format(
        date.year,
        date.month,
        date.day
    )

    file_name = loc[13:]                                        # remove the '/images/temp/'
    if not os.path.exists(new_prefix+'images/' + date_suffix):              # if the target directory doesn't exist ...
        os.makedirs(os.path.dirname(new_prefix+'images/'+date_suffix))                # ... make it.
    img = Image.open(new_prefix + loc[1:])                                 # open the image from the temp
    img.save(new_prefix+'images/'+date_suffix+file_name.lower())    # open the new location

    max_height = 500                                            # maximum height
    img = Image.open(new_prefix + loc[1:])                      # open the image in PIL
    h_percent = (max_height / float(img.size[1]))               # calculate what percentage the new height is of the old
    w_size = int((float(img.size[0]) * float(h_percent)))       # calculate the new size of the width
    img = img.resize((w_size, max_height), Image.ANTIALIAS)     # translate the image
    if not os.path.exists(old_prefix+date_suffix):              # if the blog's directory doesn't exist
        os.makedirs(os.path.dirname(old_prefix+date_suffix))    # make it
    img.save(old_prefix+date_suffix+file_name.lower())          # image save old_prefix
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory
    return "/" + date_suffix+file_name.lower()                          # of form data/yyyy/mm/dd/name.extension


def run(lines, date=None):
    # 1. find all the references to images
    ALBUM_GROUP_RE = re.compile(
        r'''(@{3,})(?P<album>((.)|(\n))*?)(@{3,})'''
    )

    text = lines
    last_index = -1
    finished = False
    while not finished:
        # given the substitution, the new entries will likely be longer
        # ie. images/temp/name.jpg is shorter than data/yyyy/mm/dd/name
        # substituting immediately in will cause overlap
        # we need this loop to go over iteratively; we keep track of where we were last with
        collections = ALBUM_GROUP_RE.finditer(text)
        if collections:
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
                        album = ""                                      # where we place reformatted images
                        for index in range(len(images)):                # for image in the whole collection
                            last_index = current_index                  # update
                            image_ref = re.search(
                                "(?<=\({1})(.)*(?=\){1})",
                                images[index]) \
                                .group()  # get the image location
                            alt = re.search(
                                "(?<=\[{1})(.)*(?=\]{1})",
                                images[index]
                            ).group()  # get the text
                            if image_ref.startswith("/images/temp/"):  # if the location is in our temp folder...
                                image_ref = move(image_ref, date)  # ... move and resize photos
                            album += "[%s](%s)" % (alt, image_ref)  # album
                            if index != len(images) - 1:  # if this isn't the last image in the set...
                                album += "-\n"  # ... then make room for another image
                        current_index = last_index
                        if album is not "":  # if the album isn't empty
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
    print text
    return text


if __name__ == "__main__":
    run(""""
@@@[](/images/temp/IMG_6224.JPG)@@@

@@@[](/images/temp/IMG_6203.JPG)-[](/images/temp/IMG_6216.JPG)-[](/images/temp/IMG_6191.JPG)@@@

@@@[](/images/temp/IMG_6208.JPG)-[](/images/temp/IMG_6225.JPG)@@@

@@@[](/images/temp/IMG_6218.JPG)@@@
""")

#     run(
# """"easter
#
# @@@
# ()[/data/2017/4/17/IMG_6224.JPG]
# @@@
#
#
# @@@
# ()[/data/2017/4/17/IMG_6203.JPG]-
# ()[/data/2017/4/17/IMG_6216.JPG]-
# ()[/data/2017/4/17/IMG_6191.JPG]
# @@@
#
#
# @@@
# ()[/data/2017/4/17/IMG_6208.JPG]-
# ()[/data/2017/4/17/IMG_6225.JPG]
# @@@
#
#
# @@@
# ()[/data/2017/4/17/IMG_6224.JPG]
# @@@
#
#
# @@@
# ()[/data/2017/4/17/IMG_6218.JPG]
# @@@
# """
#
#     )
