import re
from PIL import Image
from datetime import datetime
import os
import configparser
from pysrc.markdown_albums.markdown_album_extension import album_regexp
from pysrc.file_management.file_parser import move_and_resize

ALBUM_GROUP_RE = re.compile(album_regexp)

# Add these regex patterns
images_regexp = "(?<=\){1})[ ,\n,\r]*-*[ ,\n,\r]*(?=\[{1})"
image_ref_regexp = "(?<=\({1})(.)*(?=\){1})"
alt_text_regexp = "(?<=\[{1})(.)*(?=\]{1})"

__author__ = "kongaloosh"

config = configparser.ConfigParser()
config.read("config.ini")

ORIGINAL_PHOTOS_DIR = config.get("PhotoLocations", "BulkUploadLocation")
BLOG_STORAGE = config.get("PhotoLocations", "BlogStorage")
PERMANENT_PHOTOS_DIR = config.get("PhotoLocations", "PermStorage")


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
    file_name = loc[len(ORIGINAL_PHOTOS_DIR) :]  # remove the '/images/temp/'
    # we remove '/images/' because it's in both the prefix from the config file and the filename from the wysiwyg edit
    # todo: check to see if you can re-name the prefix in the config file to make this easier
    # this creates the absolute filepath
    target_file_path = (
        PERMANENT_PHOTOS_DIR + loc[len(ORIGINAL_PHOTOS_DIR) :]
    )  # remove the '/images/'

    # 1. SAVE THE ORIGINAL IMAGE AT ORIGINAL QUALITY
    if not os.path.exists(
        PERMANENT_PHOTOS_DIR + date_suffix
    ):  # if the target directory doesn't exist ...
        os.makedirs(os.path.dirname(PERMANENT_PHOTOS_DIR + date_suffix))  # ... make it.
    img = Image.open(target_file_path)  # open the image from the temp
    img.save(
        PERMANENT_PHOTOS_DIR + date_suffix + file_name.lower()
    )  # open the new location

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
            BLOG_STORAGE + date_suffix
        ):  # if the blog's directory doesn't exist
            os.makedirs(os.path.dirname(BLOG_STORAGE + date_suffix))  # make it
        img.save(
            BLOG_STORAGE + date_suffix + file_name.lower()
        )  # image save old_prefix
    except OSError:
        pass
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory
    os.remove(target_file_path)
    return (
        "/" + date_suffix + file_name.lower()
    )  # of form data/yyyy/mm/dd/name.extension


def run(lines: str, target_dir: str):
    """
    Finds all references to images, removes them from their temporary directory, moves
    them to their new location, and replaces references to them in the original post.
    """
    text = lines
    last_index = -1
    finished = False
    while not finished:
        collections = ALBUM_GROUP_RE.finditer(text)
        if collections:
            current_index = 0
            while True:
                try:
                    collection = next(collections)
                except StopIteration:
                    if current_index == last_index or last_index == -1:
                        finished = True
                    break
                current_index += 1
                if current_index > last_index:
                    images = re.split(images_regexp, collection.group("album"))
                    album = ""
                    for index in range(len(images)):
                        last_index = current_index
                        image_ref = re.search(image_ref_regexp, images[index]).group()
                        alt = re.search(alt_text_regexp, images[index]).group()

                        if image_ref.startswith(ORIGINAL_PHOTOS_DIR):
                            filename = os.path.basename(image_ref)
                            high_res_location = os.path.join(
                                PERMANENT_PHOTOS_DIR, target_dir, filename
                            )
                            web_size_location = os.path.join(
                                BLOG_STORAGE, target_dir, filename
                            )
                            move_and_resize(
                                image_ref,
                                web_size_location,
                                high_res_location,
                            )

                        album += "[%s](%s)" % (alt, web_size_location)
                        if index != len(images) - 1:
                            album += "-\n"

                    current_index = last_index

                    if album != "":
                        text = "%s@@@%s@@@%s" % (
                            text[: collection.start()],
                            album,
                            text[collection.end() :],
                        )
                    last_index = current_index
        else:
            finished = True
            break
    return text


if __name__ == "__main__":
    lines = "@@@\r\n[](/data/2017/7/4/img_6817.jpg)-\r\n[](/data/2017/7/4/img_0281.jpg)-\r\n[](/data/2017/7/4/img_6786.jpg)\r\n@@@"
    lines_2 = "@@@[](/images/temp/IMG_1252.jpg)-[](/images/temp/IMG_1253.jpg)@@@"

    print(run(lines, date=None))
    print(run(lines_2, date=None))
