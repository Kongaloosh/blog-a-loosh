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
from pysrc.database.queries import EntryQueries, CategoryQueries
import shutil
from pysrc.video_converter import convert_video_to_mp4
from pysrc.post import GeoLocation

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


def move_and_resize(from_location: str, to_copy: str, high_res: str) -> None:
    """Move a file from a temporary location to a permanent one."""
    try:
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(to_copy), exist_ok=True)
        os.makedirs(os.path.dirname(high_res), exist_ok=True)

        # Open and process the image
        img = Image.open(from_location)

        # Convert RGBA to RGB if necessary
        if img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        ):
            # Create a white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            # Paste the image on the background using alpha channel as mask
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img, mask=img.convert("RGBA").split()[3])
            img = background

        # Save the web-sized version
        img.thumbnail((800, 800))  # Resize for web
        img.save(to_copy, "JPEG", quality=85)

        # Save the high-res version
        img_high = Image.open(from_location)
        if img_high.mode in ("RGBA", "LA") or (
            img_high.mode == "P" and "transparency" in img_high.info
        ):
            background = Image.new("RGB", img_high.size, (255, 255, 255))
            if img_high.mode == "RGBA":
                background.paste(img_high, mask=img_high.split()[3])
            else:
                background.paste(img_high, mask=img_high.convert("RGBA").split()[3])
            img_high = background
        img_high.save(high_res, "JPEG", quality=95)

        # Clean up the original file if it's in the temporary directory
        if BULK_UPLOAD_DIR in from_location:
            os.remove(from_location)

    except Exception as e:
        app.logger.error(f"Error processing image {from_location}: {str(e)}")
        raise ValueError(f"Failed to process image: {str(e)}")


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
            for i in data["in_reply_to"]:
                if isinstance(i, dict):
                    in_reply_to.append(i)
                elif isinstance(i, str):
                    if i.startswith("http://127.0.0.1:5000") or i.startswith(
                        "https://kongaloosh.com/"
                    ):
                        reply_filename = (
                            i.replace(
                                "http://127.0.0.1:5000/e/", BLOG_STORAGE, 1
                            ).replace("https://kongaloosh.com/e/", BLOG_STORAGE, 1)
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

    # Handle geo data
    if data.get("geo"):
        if isinstance(data["geo"], dict):
            # If coordinates are stored as string, convert to tuple
            if "coordinates" in data["geo"] and isinstance(
                data["geo"]["coordinates"], str
            ):
                lat, lon = map(float, data["geo"]["coordinates"].split(","))
                data["geo"]["coordinates"] = (lat, lon)
            data["geo"] = GeoLocation(**data["geo"])

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
        assert isinstance(data, BlogPost)
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
    if not os.path.isfile(relative_post_path + ".json") or update:
        # Find all the multimedia files which were added with the posts.
        # we name the files based on the slug of the post and colocate them.
        if data.photo:
            extension = ".jpg"
            file_list = []
            for file_i in data.photo:
                # if the image is already in the blog storage directory
                # we don't need to move it. It's already where we want it.
                if isinstance(file_i, str) and file_i.startswith(BLOG_STORAGE):
                    file_list.append(file_i)
                # if the image is in the bulk upload directory
                # we need to move it to the blog storage directory.
                elif isinstance(file_i, str) and file_i.startswith(BULK_UPLOAD_DIR):
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
                    move_and_resize(
                        from_location,
                        web_size_location,
                        high_res_location,
                    )
                    file_list.append(web_size_location)

            data.photo = file_list
        if data.video:
            video_list = []
            for video_i in data.video:
                if isinstance(video_i, str):
                    if video_i.startswith(BLOG_STORAGE):
                        video_list.append(video_i)
                    elif video_i.startswith(BULK_UPLOAD_DIR):
                        new_name = f"{data.slug}-{len(video_list)}.mp4"
                        final_location = os.path.join(
                            BLOG_STORAGE, date_location, new_name
                        )

                        # Start conversion but don't wait for it
                        convert_video_to_mp4(video_i, final_location)

                        # Add the expected path to the list
                        video_list.append(
                            os.path.join(BLOG_STORAGE, date_location, new_name)
                        )

            data.video = video_list
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
            assert isinstance(data, BlogPost)
            g.execute(
                EntryQueries.INSERT, [data.slug, data.published, relative_post_path]
            )
            g.commit()

            if data.category:
                for c in data.category:
                    g.execute(
                        CategoryQueries.INSERT_OR_REPLACE,
                        [data.slug, data.published, c],
                    )
                    g.commit()
        return data.url

    else:
        return "/already_made"  # a post of this name already exists


def update_json_entry(
    data: Union[BlogPost, DraftPost],
    old_entry: Union[BlogPost, DraftPost],
    g=None,
    draft=False,
):
    """Updates a json entry with new data."""
    try:
        # Only copy published date if both objects have it
        if isinstance(data, BlogPost) and isinstance(old_entry, BlogPost):
            data.published = old_entry.published

        # Preserve other metadata
        if hasattr(old_entry, "slug"):
            data.slug = old_entry.slug
        if hasattr(old_entry, "url"):
            data.url = old_entry.url
        if hasattr(old_entry, "u_uid"):
            data.u_uid = old_entry.u_uid

        # 2. Handle photos
        new_photos = data.photo or []
        old_photos = old_entry.photo or []
        to_delete = [i for i in old_photos if i not in new_photos]

        for i in to_delete:
            if os.path.exists(i):
                os.remove(i)

        # 4. Handle videos
        new_videos = data.video or []
        old_videos = old_entry.video or []
        to_delete = [i for i in old_videos if i not in new_videos]

        app.logger.info(f"To delete: {to_delete}")
        app.logger.info(f"New videos: {new_videos}")
        app.logger.info(f"old videos: {old_videos}")

        for i in to_delete:
            if os.path.exists(i):
                os.remove(i)

        # 4. Handle categories
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

        # 5. Save the updated entry
        create_json_entry(data=data, g=g, draft=draft, update=True)

    except Exception as e:
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


def rotate_image_by_exif(image: Image.Image) -> Image.Image:
    """Rotate image according to EXIF orientation tag"""
    try:
        # Get EXIF data
        exif = image.getexif()
        if not exif:
            return image

        # Find orientation tag
        orientation = next(
            (tag for tag, name in Image.ExifTags.TAGS.items() if name == "Orientation"),
            None,
        )

        if not orientation or orientation not in exif:
            return image

        # Rotation mapping based on EXIF orientation value
        rotation_map = {
            3: 180,  # Upside down
            6: 270,  # 90 degrees right
            8: 90,  # 90 degrees left
        }

        if rotation := rotation_map.get(exif[orientation]):
            return image.rotate(rotation, expand=True)

    except Exception as e:
        app.logger.error(f"Error processing EXIF orientation: {e}")

    return image


def handle_media_file(
    file_path: str, target_dir: str, slug: str, file_type: str
) -> str:
    """
    Handles saving of media files (photos or videos)

    Args:
        file_path: Source file path
        target_dir: Directory to save the file
        slug: Post slug for naming
        file_type: Type of media ('photo' or 'video')

    Returns:
        str: Path where the file was saved
    """
    extension = ".mp4" if file_type == "video" else ".jpg"
    i = 0
    while os.path.isfile(os.path.join(target_dir, f"{slug}-{i}{extension}")):
        i += 1

    new_name = f"{slug}-{i}{extension}"

    if file_type == "video":
        # Videos only need one copy
        final_location = os.path.join(BLOG_STORAGE, target_dir, new_name)
        shutil.copy2(file_path, final_location)
        return final_location
    else:
        # Photos need two copies (high-res and web)
        high_res_location = os.path.join(PERMANENT_PHOTOS_DIR, target_dir, new_name)
        web_size_location = os.path.join(BLOG_STORAGE, target_dir, new_name)
        move_and_resize(file_path, web_size_location, high_res_location)
        return web_size_location
