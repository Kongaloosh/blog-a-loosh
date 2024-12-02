import configparser
import os
import sqlite3
from slugify import slugify
import re
import json
from pysrc.markdown_hashtags.markdown_hashtag_extension import HashtagExtension
from pysrc.markdown_albums.markdown_album_extension import AlbumExtension
import logging
from PIL import Image
import markdown as markdown
from datetime import datetime
from flask import current_app as app
from pysrc.post import BlogPost, ReplyTo, Event, DraftPost
from pydantic import ValidationError
from typing import Any, Union
from pysrc.markdown_albums.markdown_album_extension import album_regexp

ALBUM_GROUP_RE = re.compile(album_regexp)


# Add these regex patterns
images_regexp = "(?<=\){1})[ ,\n,\r]*-*[ ,\n,\r]*(?=\[{1})"
image_ref_regexp = "(?<=\({1})(.)*(?=\){1})"
alt_text_regexp = "(?<=\[{1})(.)*(?=\]{1})"

config = configparser.ConfigParser()
config.read("config.ini")

logger = logging.getLogger(__name__)

# configuration
DATABASE = config.get("Global", "Database")
DEBUG = config.get("Global", "Debug")
SECRET_KEY = config.get("Global", "DevKey")
USERNAME = config.get("SiteAuthentication", "Username")
PASSWORD = config.get("SiteAuthentication", "password")
DOMAIN_NAME = config.get("Global", "DomainName")
GEONAMES = config.get("GeoNamesUsername", "Username")
FULLNAME = config.get("PersonalInfo", "FullName")
ORIGINAL_PHOTOS_DIR = config.get("PhotoLocations", "BulkUploadLocation")
BLOG_STORAGE = config.get("PhotoLocations", "BlogStorage")
BULK_UPLOAD_DIR = config.get("PhotoLocations", "BulkUploadLocation")
DRAFTS_STORAGE = config.get("PhotoLocations", "DraftsStorage")
PERMANENT_PHOTOS_DIR = config.get("PhotoLocations", "PermStorage")

_MAX_SIZE = 3000


def resize(img: Image.Image, max_dim: int) -> Image.Image:
    """Takes an image and resizes to max size along largest dimension.
    Args:
         img: a pillow image
         max_dim: the maximum number of pixes on the largest side

    Returns:
        a pillow image
    """
    width, height = img.size
    if height > width:
        ratio = max_dim / height
        new_height = min(max_dim, height)
        new_width = int(width * ratio)
    else:
        ratio = max_dim / width
        new_width = min(max_dim, width)
        new_height = int(height * ratio)

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def move_and_resize(from_location: str, to_blog_location: str, to_copy: str) -> None:
    """
    Moves an image, scales it and stores a low-res with the blog post and a high-res
    in a long-term storage folder.
    """
    to_blog_location = to_blog_location.lower()
    to_copy = to_copy.lower()

    os.makedirs(os.path.dirname(to_copy), exist_ok=True)
    os.makedirs(os.path.dirname(to_blog_location), exist_ok=True)

    with Image.open(from_location) as img:
        img.save(to_copy, "JPEG")
        resized_img = resize(img, _MAX_SIZE)
        resized_img.save(to_blog_location, "JPEG")

    os.remove(from_location)


def save_to_two(image: str, to_blog_location: str, to_copy: str) -> None:
    """
    Saves two images: one original and one scaled down for optimized serving.

    :param image: Path to the source image
    :param to_blog_location: Path to save the scaled-down image
    :param to_copy: Path to save the original-size image
    """
    to_blog_location = to_blog_location.lower()
    to_copy = to_copy.lower()

    os.makedirs(os.path.dirname(to_copy), exist_ok=True)
    os.makedirs(os.path.dirname(to_blog_location), exist_ok=True)

    with Image.open(image) as img:
        # Save original size image
        img_rgb = img.convert("RGB")
        img_rgb.save(to_copy, "JPEG")

        # Save resized image
        img_resized = resize(img_rgb, _MAX_SIZE)
        img_resized.save(to_blog_location, "JPEG")
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory


def file_parser_json(filename: str, md: bool = True) -> Union[BlogPost, DraftPost]:
    """
    Parses a json file into a BlogPost object.
    """
    with open(filename, "rb") as f:
        data = json.load(f)

    try:
        # Convert datetime strings to datetime objects
        if "published" in data and isinstance(data["published"], str):
            data["published"] = datetime.fromisoformat(data["published"])
        if "updated" in data and isinstance(data["updated"], str):
            data["updated"] = datetime.fromisoformat(data["updated"])

        # Handle nested Event data
        if "event" in data and isinstance(data["event"], dict):
            for key in ["dt_start", "dt_end"]:
                if key in data["event"] and isinstance(data["event"][key], str):
                    data["event"][key] = datetime.fromisoformat(data["event"][key])

        # Handle nested Travel data
        if "travel" in data and isinstance(data["travel"], dict):
            if "trips" in data["travel"]:
                for trip in data["travel"]["trips"]:
                    if "date" in trip and isinstance(trip["date"], str):
                        trip["date"] = datetime.fromisoformat(trip["date"])

        # Parse markdown content
        if md and data.get("content"):
            data["raw_content"] = data["content"]
            data["content"] = markdown.markdown(
                data["content"],
                extensions=[
                    "mdx_math",
                    AlbumExtension(),
                    HashtagExtension(),
                    "fenced_code",
                ],
            )
        elif data.get("content") is None:
            data["content"] = ""
            data["raw_content"] = ""

        # Handle in_reply_to
        if data.get("in_reply_to"):
            in_reply_to = []
            # TODO: This is a hack to make sure that the in_reply_to is a list.
            #  We should fix it so that it's always a list. I can write a script.
            # if not isinstance(data["in_reply_to"], list):
            #     data["in_reply_to"] = [
            #         reply.strip() for reply in data["in_reply_to"].split(",")
            #     ]
            for i in data["in_reply_to"]:
                # TODO: I don't think this is used anywhere. Write a script to check.
                # if isinstance(i, dict):
                # in_reply_to.append(i)
                if i.startswith("http://127.0.0.1:5000") or i.startswith(
                    "https://kongaloosh.com/"
                ):
                    # if this is a local reply to myself.
                    reply_filename = (
                        i.replace("http://127.0.0.1:5000/e/", "data/", 1).replace(
                            "https://kongaloosh.com/e/", "data/", 1
                        )
                        + ".json"
                    )
                    in_reply_to.append(file_parser_json(reply_filename))
                elif i.startswith("http"):
                    in_reply_to.append({"url": i})
            data["in_reply_to"] = in_reply_to

        # Choose model based on file location
        if DRAFTS_STORAGE in filename:
            return DraftPost(**data)
        return BlogPost(**data)
    except ValidationError as e:
        app.logger.error(f"Validation error for {filename}: {e}")
        raise
    except json.JSONDecodeError as e:
        app.logger.error(f"JSON decode error for {filename}: {e}")
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error for {filename}: {e}")
        raise


def slug_from_post(data: dict[str, Any]) -> str:
    """
    Returns a slug for a post.
    """
    if data.get("title"):
        return slugify.slugify(data["title"])[:10]
    elif data.get("content"):
        return slugify.slugify(data["content"].split(".")[0])[:10]
    else:
        return slugify.slugify(data["published"].date().isoformat())


def save_map_file(map_data: bytes, file_path: str) -> str:
    """
    Saves map data to a file and returns the file path.

    Args:
        map_data: Raw binary map data
        file_path: Base path for the file (without extension)

    Returns:
        str: Path to the saved map file
    """
    map_file_path = f"{file_path}-map.png"
    with open(map_file_path, "wb") as f:
        f.write(map_data)
    return map_file_path


def create_post_from_data(
    data: BlogPost | DraftPost | dict[str, Any]
) -> Union[BlogPost, DraftPost]:
    # Convert Pydantic models to dict first
    if isinstance(data, (BlogPost, DraftPost)):
        data = data.model_dump()

    # 1. Clean up None values
    data = {k: v for k, v in data.items() if v not in (None, "", "None")}

    # Ensure required fields have at least empty values
    data["content"] = data.get("content") or ""  # Default to empty string if None

    # 2. Generate slug if missing
    if not data.get("slug"):
        if data.get("title"):
            data["slug"] = slugify(data["title"])[:50]
        elif data.get("content"):
            data["slug"] = slugify(data["content"].split(".")[0])[:50]
        else:
            data["slug"] = slugify(data["published"].date().isoformat())

    # 3. Handle categories
    if data.get("category"):
        if isinstance(data["category"], str):
            data["category"] = [cat.strip() for cat in data["category"].split(",")]

    # 3. Parse reply-tos
    if data.get("in_reply_to"):
        if isinstance(data["in_reply_to"], str):
            data["in_reply_to"] = [
                reply.strip() for reply in data["in_reply_to"].split(",")
            ]
        elif isinstance(data["in_reply_to"], list):
            data["in_reply_to"] = [
                ReplyTo(url=reply["url"]) if isinstance(reply, dict) else reply
                for reply in data["in_reply_to"]
            ]

    # 4. Ensure published is a datetime object
    if isinstance(data.get("published"), str):
        data["published"] = datetime.fromisoformat(data["published"])

    # 5. Handle event data
    if data.get("event_name") or data.get("dt_start") or data.get("dt_end"):
        data["event"] = Event(
            event_name=data.get("event_name"),
            dt_start=data.get("dt_start"),
            dt_end=data.get("dt_end"),
        )

    # 6. Create and validate BlogPost
    try:
        return BlogPost(**data)
    except ValidationError:
        try:
            return DraftPost(**data)
        except ValidationError as e:
            raise ValueError(f"Invalid blog post data: {e}")


def create_json_entry(
    data: Union[BlogPost, DraftPost], g, draft: bool = False, update: bool = False
) -> str:
    """
    creates a json entry based on recieved dictionary
    """

    data = create_post_from_data(data)

    if draft:  # whether or not this is a draft changes the location saved
        directory_of_post = DRAFTS_STORAGE
        data.url = os.path.join(DRAFTS_STORAGE, data.slug)

    else:  # if it's not a draft we need to prep for saving
        date_location = "{year}/{month}/{day}/".format(
            year=str(data.published.year),
            month=str(data.published.month),
            day=str(data.published.day),
        )  # turn date into file-path
        directory_of_post = os.path.join(
            BLOG_STORAGE, date_location
        )  # where we'll save the new entry
        data.url = "/e/" + date_location + data.slug
        data.content = run(
            data.content,
            target_dir=f"{data.published.year}/{data.published.month}/{data.published.day}/",
        )

    if not os.path.exists(directory_of_post):  # if the path doesn't exist, make it
        os.makedirs(os.path.dirname(directory_of_post))

    relative_post_path = os.path.join(directory_of_post, data.slug)

    # check to make sure that the .json and human-readable versions do not exist currently
    if (
        not os.path.isfile(relative_post_path + ".md")
        and not os.path.isfile(relative_post_path + ".json")
        or update
    ):
        # Find all the multimedia files which were added with the posts.
        # we name the files based on the slug of the post and colocate them.
        if data.photo:
            extension = ".jpg"
            file_list = []
            for file_i in data.photo:
                # if the image is a location ref
                if isinstance(file_i, str) and file_i.startswith(BULK_UPLOAD_DIR):
                    i = 0
                    while os.path.isfile(relative_post_path + "-" + str(i) + extension):
                        i += 1

                    from_location = file_i
                    new_name = data.slug + "-" + str(i) + extension
                    high_res_location = os.path.join(
                        PERMANENT_PHOTOS_DIR, date_location, new_name
                    )
                    web_size_location = os.path.join(
                        BLOG_STORAGE, date_location, new_name
                    )
                    print(f"high_res_location: {high_res_location}")
                    print(f"web_size_location: {web_size_location}")
                    print(f"from_location: {from_location}")
                    print("\n\n\n\n\n\n\n\n\n\n")
                    move_and_resize(
                        from_location,
                        web_size_location,
                        high_res_location,
                    )

                    file_list.append(web_size_location)

            data.photo = file_list
        try:
            if data.travel and data.travel.map_data:
                map_file_path = save_map_file(data.travel.map_data, relative_post_path)
                data.travel.map_path = map_file_path
                data.travel.map_data = None

        except (KeyError, AttributeError) as e:
            logger.error(f"Error saving map file: {e}")

        json_data = data.model_dump(mode="json")

        with open(relative_post_path + ".json", "w") as file_writer:
            json.dump(json_data, file_writer)

        if not draft and not update and g:  # if this isn't a draft, put it in the dbms
            g.execute(
                """
                insert into entries
                (slug, published, location) values (?, ?, ?)
                """,
                [data.slug, data.published, relative_post_path],
            )
            g.commit()
            if data.category:
                for c in data.category:
                    g.execute(
                        "insert or replace into categories (slug, published, category) values (?, ?, ?)",  # noqa
                        [data.slug, data.published, c],
                    )
                    g.commit()
        return data.url

    else:
        return "/already_made"  # a post of this name already exists


def update_json_entry(
    data: BlogPost, old_entry: BlogPost, g: sqlite3.Connection, draft: bool = False
) -> None:
    """Update old entry based on differences in new entry and saves file."""
    try:
        # 1. Preserve privileged old info
        data.slug = old_entry.slug
        data.url = old_entry.url
        data.published = old_entry.published

        # 2. Handle photos
        old_photos = data.photo or []
        to_delete = [i for i in (old_entry.photo or []) if i not in old_photos]

        for i in to_delete:
            if os.path.exists(i):
                os.remove(i)

        # 3. Handle categories
        if data.category and not draft and g:
            # Delete old categories
            for c in old_entry.category or []:
                g.execute(
                    "DELETE FROM categories WHERE slug = ? AND category = ?",
                    (data.slug, c),
                )

            # Insert new categories
            for c in data.category:
                g.execute(
                    "INSERT OR REPLACE INTO categories (slug, published, category) VALUES (?, ?, ?)",
                    [data.slug, data.published, c],
                )
            g.commit()

        # 4. Save the updated entry
        create_json_entry(data=data, g=g, draft=draft, update=True)

    except Exception as e:
        app.logger.error(f"Error in update_json_entry: {e}")
        raise ValueError(f"Failed to update entry: {str(e)}")


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
