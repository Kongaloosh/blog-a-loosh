import re
from PIL import Image
from datetime import datetime
import os
import configparser
from pysrc.markdown_albums.markdown_album_extension import album_regexp

ALBUM_GROUP_RE = re.compile(album_regexp)

__author__ = "kongaloosh"


config = configparser.ConfigParser()
config.read("config.ini")

ORIGINAL_PHOTOS_DIR = config.get("PhotoLocations", "BulkUploadLocation")

old_prefix = config.get("PhotoLocations", "BlogStorage")
new_prefix = config.get("PhotoLocations", "PermStorage")


def move(loc, date):
    """ "
    Moves an image, scales it and stores a low-res with the blog post and a high-res in a long-term storage folder.
    :param loc: the location of an image
    :param loc: the date folder to which an image should be moved
    """
    if date is None:
        date = datetime.now()

    date_suffix = "data/{0}/{1}/{2}/".format(date.year, date.month, date.day)
    # loc is where the temp image is that we're trying to resize and move
    # we get the filename--without the relative folder structure---to use in the new savenames
    file_name = loc[len("/images/temp/") :]  # remove the '/images/temp/'
    # we remove '/images/' because it's in both the prefix from the config file and the filename from the wysiwyg edit
    # todo: check to see if you can re-name the prefix in the config file to make this easier
    # this creates the absolute filepath
    target_file_path = new_prefix + loc[len("/images/") :]  # remove the '/images/'

    # 1. SAVE THE ORIGINAL IMAGE AT ORIGINAL QUALITY
    if not os.path.exists(
        new_prefix + date_suffix
    ):  # if the target directory doesn't exist ...
        os.makedirs(os.path.dirname(new_prefix + date_suffix))  # ... make it.
    img = Image.open(target_file_path)  # open the image from the temp
    img.save(new_prefix + date_suffix + file_name.lower())  # open the new location

    # 2. RESIZE IMAGE AND SAVE FOR BLOG SERVING
    max_height = 1000  # maximum height
    img = Image.open(target_file_path)  # open the image in PIL
    h_percent = max_height / float(
        img.size[1]
    )  # calculate what percentage the new height is of the old
    w_size = int(
        (float(img.size[0]) * float(h_percent))
    )  # calculate the new size of the width
    img = img.resize((w_size, max_height), Image.ANTIALIAS)  # translate the image
    try:
        if not os.path.exists(
            old_prefix + date_suffix
        ):  # if the blog's directory doesn't exist
            os.makedirs(os.path.dirname(old_prefix + date_suffix))  # make it
        img.save(old_prefix + date_suffix + file_name.lower())  # image save old_prefix
    except OSError:
        pass
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory
    os.remove(target_file_path)
    return (
        "/" + date_suffix + file_name.lower()
    )  # of form data/yyyy/mm/dd/name.extension


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
        if collections:  # if there's an image match
            current_index = 0
            while True:
                try:
                    collection = collections.next()
                    current_index += 1
                    if current_index > last_index:
                        # split a daisy chain of images in an album
                        images = re.split(  # split the collection into images
                            "(?<=\){1})[ ,\n,\r]*-*[ ,\n,\r]*(?=\[{1})",
                            collection.group("album"),
                        )
                        album = ""  # where we place reformatted images
                        for index in range(
                            len(images)
                        ):  # for image in the whole collection
                            last_index = current_index  # update

                            image_ref = re.search(
                                "(?<=\({1})(.)*(?=\){1})", images[index]
                            ).group()  # get the image location

                            alt = re.search(
                                "(?<=\[{1})(.)*(?=\]{1})", images[index]
                            ).group()  # get the text

                            if image_ref.startswith(
                                "/images/temp/"
                            ):  # if the location is in our temp folder...
                                image_ref = move(
                                    image_ref, date
                                )  # ... move and resize photos
                            album += "[%s](%s)" % (alt, image_ref)  # album
                            if (
                                index != len(images) - 1
                            ):  # if this isn't the last image in the set...
                                album += "-\n"  # ... then make room for another image

                        current_index = last_index

                        if album != "":  # if the album isn't empty
                            text = "%s@@@%s@@@%s" % (
                                text[
                                    : collection.start()
                                ],  # sub it into where the old images were
                                album,
                                text[collection.end() :],
                            )
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
    lines = "@@@\r\n[](/data/2017/7/4/img_6817.jpg)-\r\n[](/data/2017/7/4/img_0281.jpg)-\r\n[](/data/2017/7/4/img_6786.jpg)\r\n@@@"
    lines_2 = "@@@[](/images/temp/IMG_1252.jpg)-[](/images/temp/IMG_1253.jpg)@@@"

    print(run(lines, date=None))
    print(run(lines_2, date=None))
