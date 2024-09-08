import configparser
import re
import os
import sqlite3
import sys
import slugify
import json
from dateutil.parser import parse
from pysrc.markdown_hashtags.markdown_hashtag_extension import HashtagExtension
from pysrc.markdown_albums.markdown_album_extension import AlbumExtension
from pysrc.file_management.markdown_album_pre_process import new_prefix
import logging
from PIL import Image
import markdown as markdown
from datetime import datetime
from flask import current_app as app
from pysrc.post import BlogPost, ReplyTo, Event
from pydantic import HttpUrl, ValidationError
from typing import Any


sys.path.insert(0, os.getcwd())  # todo: this is bad.

__author__ = "kongaloosh"

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


def file_parser_json(filename: str, md: bool = True) -> BlogPost:
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


def create_post_from_data(data: dict[str, Any]) -> BlogPost:
    """
    Cleans and prepares a dictionary based on posted form info for JSON dump.
    Returns a validated BlogPost object.
    """
    # 1. Create slug if not present
    if not data.get("slug"):
        slug = slug_from_post(data)
        data["slug"] = slug
        data["u_uid"] = slug

    # 2. Parse categories
    if isinstance(data.get("category"), str):
        data["category"] = [cat.strip().lower() for cat in data["category"].split(",")]

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
    except ValidationError as e:
        raise ValueError(f"Invalid blog post data: {e}")


def create_json_entry(data, g, draft=False, update=False) -> str:
    """
    creates a json entry based on recieved dictionary
    """

    data = create_post_from_data(data)

    if draft:  # whether or not this is a draft changes the location saved
        file_path = "drafts/"
        data.url = "/drafts/" + data.slug

    else:  # if it's not a draft we need to prep for saving
        date_location = "{year}/{month}/{day}/".format(
            year=str(data.published.year),
            month=str(data.published.month),
            day=str(data.published.day),
        )  # turn date into file-path
        file_path = "data/" + date_location  # where we'll save the new entry
        data.url = "/e/" + date_location + data.slug

    if not os.path.exists(file_path):  # if the path doesn't exist, make it
        os.makedirs(os.path.dirname(file_path))

    total_path = file_path + "{slug}".format(slug=data.slug)  # path including filename

    # check to make sure that the .json and human-readable versions do not exist currently
    if (
        not os.path.isfile(total_path + ".md")
        and not os.path.isfile(total_path + ".json")
        or update
    ):
        # Find all the multimedia files which were added with the posts
        if data.photo:
            extension = ".jpg"
            i = 0
            file_list = []
            for file_i in data.photo:
                if file_i:  # if there is no photo already
                    # if the image is a location ref
                    if isinstance(file_i, str) and file_i.startswith("/images/"):
                        # print("is unnicode and is /img/", file_i)
                        while os.path.isfile(total_path + "-" + str(i) + extension):
                            i += 1
                        # move the image and resize it
                        move_and_resize(
                            new_prefix
                            + file_i[
                                len("/images/") :
                            ],  # we remove the head to get rid of preceeding "/images/"
                            total_path + "-" + str(i) + extension,
                            new_prefix + total_path + "-" + str(i) + extension,
                        )
                        file_list.append(
                            new_prefix + total_path + "-" + str(i) + extension
                        )
                    elif isinstance(
                        file_i, str
                    ):  # if we have a buffer with the data already present, simply save and move it.
                        # print("Is unicode, but not new", file_i)
                        file_list.append(file_i)
                    else:
                        # print("Is not unicode, and is new", file_i)
                        while os.path.isfile(total_path + "-" + str(i) + extension):
                            i += 1
                        save_to_two(
                            file_i,
                            total_path + "-" + str(i) + extension,
                            new_prefix + total_path + "-" + str(i) + extension,
                        )
                        file_list.append(
                            total_path + "-" + str(i) + extension
                        )  # update the dict to a location refrence
                i += 1

            data.photo = file_list
        try:
            if data.travel and data.travel.map:
                # TODO: this is messed up if the map is a url.
                file_writer = open(total_path + "-map.png", "wb")
                file_writer.write(data.travel.map)  # save the buffer from the request
                file_writer.close()
                data.travel.map = (
                    total_path + "-map.png"
                )  # where the post should point to fetch the map
        except KeyError:
            pass

        file_writer = open(
            total_path + ".json", "w"
        )  # open and dump the actual post meta-data
        file_writer.write(json.dumps(data))
        file_writer.close()

        if not draft and not update and g:  # if this isn't a draft, put it in the dbms
            g.db.execute(
                """
                insert into entries
                (slug, published, location) values (?, ?, ?)
                """,
                [data.slug, data.published, total_path],
            )
            g.db.commit()
            if data.category:
                for c in data.category:
                    g.db.execute(
                        "insert or replace into categories (slug, published, category) values (?, ?, ?)",  # noqa
                        [data.slug, data.published, c],
                    )
                    g.db.commit()
        return data.url

    else:
        return "/already_made"  # a post of this name already exists


def update_json_entry(
    data: dict, old_entry: dict, g: sqlite3.Connection, draft: bool = False
) -> None:
    """
    Update old entry based on differences in new entry and saves file.
    """
    # 1. Preserve privileged old info
    for key in ["slug", "u-uid", "url", "published"]:
        data[key] = old_entry[key]

    # 2. Handle photos
    old_photos = data.pop("old_photos", [])
    new_uploads = data.pop("photo", [])

    old_photos = (
        [i.strip() for i in old_photos.split(",")]
        if isinstance(old_photos, str)
        else old_photos
    )
    to_delete = [i for i in old_entry.get("photo", []) if i not in old_photos]

    for i in to_delete:
        if os.path.exists(i):
            os.remove(i)

    data["photo"] = old_photos + new_uploads if new_uploads else old_photos
    data["photo"] = data["photo"] or None

    # 3. Handle categories
    if data.get("category") and not draft and g:
        data["category"] = (
            [i.strip().lower() for i in data["category"].split(",")]
            if isinstance(data["category"], str)
            else data["category"]
        )

        for c in old_entry.get("category", []):
            g.db.execute(
                "DELETE FROM categories WHERE slug = ? AND category = ?",
                (data["slug"], c),
            )

        for c in data["category"]:
            g.db.execute(
                "INSERT OR REPLACE INTO categories (slug, published, category) VALUES (?, ?, ?)",
                [old_entry["slug"], old_entry["published"], c],
            )
        g.db.commit()

    # 4. Handle in_reply_to
    if isinstance(data.get("in_reply_to"), str):
        data["in_reply_to"] = [
            reply.strip() for reply in data["in_reply_to"].split(",")
        ]

    # 5. Validate data using BlogPost model
    try:
        updated_post = BlogPost(**data)
    except ValidationError as e:
        raise ValueError(f"Invalid blog post data: {e}")

    # 6. Update old_entry with validated data
    old_entry.update(updated_post.dict(exclude_unset=True))

    # 7. Save the updated entry
    create_json_entry(data=old_entry, g=g, draft=draft, update=True)
