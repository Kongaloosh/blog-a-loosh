#!/usr/bin/python
# coding: utf-8
import configparser
from functools import wraps
import json
from typing import List, Optional, Union, Tuple
import markdown
import os
from pysrc.file_management.file_parser import run
from pydantic import ValidationError
import requests
import sqlite3
from PIL import Image, ExifTags
from contextlib import closing
from datetime import datetime
from dateutil.parser import parse
from flask import (
    Flask,
    Request,
    request,
    session,
    g,
    redirect,
    url_for,
    abort,
    render_template,
    flash,
    make_response,
    jsonify,
    Blueprint,
    Response,
)
from werkzeug.datastructures import FileStorage
from jinja2 import Environment
from pysrc.markdown_hashtags.markdown_hashtag_extension import HashtagExtension
from pysrc.markdown_albums.markdown_album_extension import AlbumExtension
from pysrc.post import BlogPost, Event, PlaceInfo, Travel, Trip, DraftPost, GeoLocation
from pysrc.python_webmention.mentioner import get_mentions
from slugify import slugify
from pysrc.file_management.file_parser import (
    create_json_entry,
    create_post_from_data,
    update_json_entry,
    file_parser_json,
)
from dataclasses import dataclass
import uuid
from werkzeug.utils import secure_filename
import yaml
from pysrc.database.queries import EntryQueries, CategoryQueries
from flask_wtf.csrf import CSRFProtect, generate_csrf
from pydantic import HttpUrl, AnyHttpUrl


jinja_env = Environment()
jinja_env.globals.update(now=datetime.now)

config = configparser.ConfigParser()
config.read("config.ini")

# configuration
DATABASE = config.get("Global", "Database")
DEBUG = config.get("Global", "Debug")
SECRET_KEY = config.get("Global", "DevKey")
USERNAME = config.get("SiteAuthentication", "Username")
PASSWORD = config.get("SiteAuthentication", "password")
DOMAIN_NAME = config.get("Global", "DomainName")
GEONAMES = config.get("GeoNamesUsername", "Username")
FULLNAME = config.get("PersonalInfo", "FullName")
GOOGLE_MAPS_KEY = config.get("GoogleMaps", "key")
# the url to use for showing recent bulk uploads
BLOG_STORAGE = config.get("PhotoLocations", "BlogStorage")
BULK_UPLOAD_DIR = config.get("PhotoLocations", "BulkUploadLocation")
PERMANENT_PHOTOS_DIR = config.get("PhotoLocations", "PermStorage")
DRAFT_STORAGE = config.get("PhotoLocations", "DraftsStorage")

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config["STATIC_FOLDER"] = os.getcwd()
app.jinja_env.globals.update(now=datetime.now)

# Initialize CSRF protection - move this here, right after app creation
csrf = CSRFProtect(app)


@app.context_processor
def inject_csrf_token():
    token = generate_csrf()
    return dict(csrf_token=token)


# Add a second static folder specifically for serving photos
photos = Blueprint(
    "blog_data_storage",
    __name__,
    static_url_path=f"/{BLOG_STORAGE}",
    static_folder=os.path.join(os.getcwd(), BLOG_STORAGE),
)

temp_photos = Blueprint(
    "temp_photos_data_storage",
    __name__,
    static_url_path=f"/{BULK_UPLOAD_DIR}",
    static_folder=os.path.join(os.getcwd(), BULK_UPLOAD_DIR),
)

high_res_storage = Blueprint(
    "perm_photos_data_storage",
    __name__,
    static_url_path="/images",
    static_folder=PERMANENT_PHOTOS_DIR,
)

app.register_blueprint(photos)
app.register_blueprint(temp_photos)
app.register_blueprint(high_res_storage)

cfg = None


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


def connect_db() -> sqlite3.Connection:
    return sqlite3.connect(app.config["DATABASE"])


@app.errorhandler(500)
def it_broke(error):
    return render_template("it_broke.html")


@app.errorhandler(404)
def not_found(error) -> str:
    return render_template("page_not_found.html")


@app.before_request
def before_request():
    """Establish a database connection before each request.

    This function runs before every request and sets up a database
    connection, storing it in Flask's 'g' object for use during
    the request lifecycle."""
    g.db = connect_db()


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in first")  # Optional: add a message
            return redirect(url_for("show_entries")), 401  # Redirect to main index
        return f(*args, **kwargs)

    return decorated


@app.teardown_request
def teardown_request(exception):
    """Close the database connection after each request."""
    db = getattr(g, "db", None)
    if db is not None:
        db.close()


def get_entries_by_date() -> List[BlogPost]:
    """Get all entries from the database, ordered by date.

    Returns:
        List of entries, each represented as a dictionary.
    """
    entries = []
    cur = g.db.execute(EntryQueries.SELECT_ALL)
    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            try:
                entries.append(file_parser_json(row + ".json"))
            except json.JSONDecodeError:
                app.logger.error(f"Invalid JSON in file: {row}.json")
                continue
    return entries


def get_most_popular_tags() -> List[str]:
    """Get tags in descending order of usage, excluding post type declarations.

    Returns:
        List of tags in descending order by usage.
    """
    cur = g.db.execute(CategoryQueries.SELECT_POPULAR)
    return [row[0] for row in cur.fetchall()]


def resolve_placename(location: str) -> PlaceInfo:
    """
    Given a location, returns the closest placename and geoid of a location.
    Args:
        location (str): the geocoords of some location in the format 'geo:lat,long'
    Returns:
        Optional[PlaceInfo]: the placename info of the resolved place, or None.
    Raises:
        ValueError: If location format is invalid or API request fails
    """
    try:
        if not location.startswith("geo:"):
            raise ValueError("Invalid location format: must start with 'geo:'")

        coords = location[4:].split(",")
        if len(coords) != 2:
            raise ValueError("Invalid location format: must be 'geo:lat,long'")

        lat, long = coords
        long = long.split(";")[0]  # Remove any additional parameters after semicolon

        url = f"http://api.geonames.org/findNearbyPlaceNameJSON?style=Full&radius=5&lat={lat}&lng={long}&username={GEONAMES}"
        geo_results = requests.get(url).json()

        if not geo_results.get("geonames"):
            raise ValueError("No geonames api key found")

        place_info = geo_results["geonames"][0]
        place_name = place_info["name"]
        admin_name = None

        for admin_level in ["adminName2", "adminName1"]:
            if place_info.get(admin_level):
                admin_name = place_info[admin_level]
                break

        return PlaceInfo(
            name=place_name,
            geoname_id=place_info["geonameId"],
            admin_name=admin_name,
            country_name=place_info.get("countryName"),
        )
    except (IndexError, KeyError, requests.RequestException, ValidationError) as e:
        raise ValueError(f"Error resolving placename: {e}")


@dataclass
class PostFormData:
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[List[str]] = None
    published: Optional[datetime] = None
    in_reply_to: Optional[List[str]] = None
    geo: Optional[GeoLocation] = None
    event: Optional[Event] = None
    travel: Optional[Travel] = None
    photo: Optional[List[str]] = None
    video: Optional[List[str]] = None


def process_form_data(request: Request) -> PostFormData:
    """Process only the form fields from the request"""
    data = PostFormData()

    # Basic text fields
    data.title = request.form.get("title")
    data.content = request.form.get("content")
    data.summary = request.form.get("summary")

    # Handle categories/tags
    if category := request.form.get("category"):
        data.category = [cat.strip() for cat in category.split(",")]

    # Handle published date
    if published := request.form.get("published"):
        data.published = parse(published)
    else:
        data.published = datetime.now()

    # Handle reply-to
    if reply_to := request.form.get("in_reply_to"):
        data.in_reply_to = [r.strip() for r in reply_to.split(",")]

    # Handle existing photos
    if photo_list := request.form.get("photo"):
        app.logger.info(f"Photo list: {photo_list}")
        data.photo = [p.strip() for p in photo_list.split(",")]

    # Handle existing videos
    if video_list := request.form.get("video"):
        app.logger.info(f"Video list: {video_list}")
        data.video = [v.strip() for v in video_list.split(",")]

    # Handle location/geo data
    if coordinates := request.form.get("geo_coordinates"):
        try:
            lat, lon = [float(x) for x in coordinates.split(",")]
            data.geo = GeoLocation(
                coordinates=(lat, lon),
                name=request.form.get("geo_name"),
                location_id=(
                    int(request.form.get("geo_id"))
                    if request.form.get("geo_id")
                    else None
                ),
                raw_location=request.form.get("geo_raw"),
            )
        except (ValueError, TypeError) as e:
            app.logger.error(f"Error processing coordinates {coordinates}: {e}")
            # Skip setting geo if coordinates are invalid

    return data


def handle_uploaded_files(request: Request) -> Tuple[List[str], List[str]]:
    """Handle both photo and video file uploads, returns paths to saved files"""
    photo_paths: List[str] = []
    video_paths: List[str] = []

    # Debug request information
    app.logger.info(f"Form data keys: {list(request.form.keys())}")
    app.logger.info(f"Files keys: {list(request.files.keys())}")
    app.logger.info(f"Content type: {request.content_type}")

    upload_dir = os.path.join(os.getcwd(), BULK_UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)

    files = request.files.getlist("media_file[]")
    app.logger.info(f"Number of files: {len(files)}")

    if files:
        for file in files:
            if file.filename:
                app.logger.info(
                    f"Processing file: {file.filename} of type {file.content_type}"
                )
                filename = secure_filename(file.filename)
                path = os.path.join(upload_dir, filename)

                if file.filename.lower().endswith(
                    (".mp4", ".mov", ".qt", ".m4v", ".avi", ".wmv", ".flv", ".mkv")
                ):
                    try:
                        file_size_before = len(file.read())
                        file.stream.seek(0)
                        app.logger.info(
                            f"Video file size before save: {file_size_before}"
                        )

                        with open(path, "wb") as f:
                            content = file.read()
                            f.write(content)
                            app.logger.info(f"Wrote {len(content)} bytes to {path}")

                        final_size = os.path.getsize(path)
                        app.logger.info(f"Final file size: {final_size}")

                        if final_size == 0:
                            app.logger.error(
                                f"Video file {filename} is empty after save"
                            )
                            continue

                        video_paths.append(os.path.join(BULK_UPLOAD_DIR, filename))
                    except Exception as e:
                        app.logger.error(f"Error saving video {filename}: {str(e)}")
                        app.logger.exception(e)
                else:
                    # Handle image with rotation
                    try:
                        image = Image.open(file.stream)
                        rotated_image = rotate_image_by_exif(image)
                        rotated_image.save(path)
                        photo_paths.append(os.path.join(BULK_UPLOAD_DIR, filename))
                    except Exception as e:
                        app.logger.error(f"Error processing image {filename}: {str(e)}")
                        file.save(path)
                        photo_paths.append(os.path.join(BULK_UPLOAD_DIR, filename))

        return photo_paths, video_paths

    return [], []


def post_from_request(
    request: Request, existing_post: Optional[Union[BlogPost, DraftPost]] = None
) -> Union[BlogPost, DraftPost]:
    """Process form data into a Post model based on the form action"""
    try:
        form_data = process_form_data(request)
        photo_paths, video_paths = handle_uploaded_files(request)

        # Get both existing and new media paths
        existing_photos = (
            request.form.get("existing_photos", "").split(",")
            if request.form.get("existing_photos")
            else []
        )

        # Get existing videos
        existing_videos = (
            request.form.get("existing_videos", "").split(",")
            if request.form.get("existing_videos")
            else []
        )

        # Filter out empty strings
        existing_photos = [path for path in existing_photos if path.strip()]
        existing_videos = [path for path in existing_videos if path.strip()]

        app.logger.info(f"Existing photos: {existing_photos}")
        app.logger.info(f"New photos: {photo_paths}")
        app.logger.info(f"Existing videos: {existing_videos}")
        app.logger.info(f"New videos: {video_paths}")
        app.logger.info(f"All photos: {existing_photos + photo_paths}")
        app.logger.info(f"All videos: {existing_videos + video_paths}")

        # Base post data with safe list handling
        post_data = {
            "title": form_data.title,
            "content": form_data.content,
            "summary": form_data.summary,
            "category": form_data.category,
            "photo": existing_photos + photo_paths,
            "video": existing_videos + video_paths,
            "in_reply_to": form_data.in_reply_to,
            "geo": form_data.geo,
            "travel": (
                handle_travel_data(request)
                if "geo[]" in request.form and request.form.getlist("geo[]")[0]
                else Travel()
            ),
            "event": handle_event_data(request),
        }

        if existing_post:
            # Preserve existing data
            post_data.update(
                {
                    "slug": existing_post.slug,
                    "url": existing_post.url,
                }
            )
            if isinstance(existing_post, BlogPost):
                post_data.update(
                    {
                        "published": existing_post.published,
                        "u_uid": existing_post.u_uid,
                    }
                )

            return type(existing_post)(**post_data)
        elif "Save" in request.form:
            if publish_date := request.form.get("publish_date"):
                date = parse(publish_date)
            else:
                date = datetime.now()
            post_data.update(
                {
                    "slug": (
                        slugify(form_data.title)
                        if form_data.title
                        else f"draft-{date.timestamp()}"
                    ),
                    "url": f"/drafts/{date.strftime('%Y/%m/%d')}/untitled",
                    "published": date,
                    "u_uid": str(uuid.uuid4()),
                }
            )
            return DraftPost(**post_data)
        else:
            if publish_date := request.form.get("publish_date"):
                date = parse(publish_date)
            else:
                date = datetime.now()

            post_data.update(
                {
                    "slug": "",
                    "url": "",
                    "published": date,
                    "u_uid": str(uuid.uuid4()),
                }
            )
            return BlogPost(**post_data)

    except TravelValidationError:
        raise
    except Exception as e:
        flash(f"Error creating post: {str(e)}", "error")
        raise ValueError(f"Invalid blog post data: {e}")


def handle_photo_files(request: Request) -> List[FileStorage]:
    files = request.files.getlist("photo_file[]")
    if files:
        return files
    # TODO: This is another situation where I should just write a
    # script to make sure old posts are formatted correctly. so we
    # don't have to do this.
    photo_file = request.files.get("photo_file")
    if photo_file:
        photo_file.seek(0, 2)
        if photo_file.tell() > 0:
            photo_file.seek(0)
            return [photo_file]
    raise ValueError("No photo files found")


class TravelValidationError(ValueError):
    pass


def handle_travel_data(request: Request) -> Travel:
    geo = request.form.getlist("geo[]")
    location = request.form.getlist("location[]")
    date = request.form.getlist("date[]")

    # Validate that we have dates for all locations
    missing_dates = []
    for i, (geo_i, location_i, date_i) in enumerate(zip(geo, location, date), 1):
        if geo_i and location_i and not date_i:  # If we have location but no date
            missing_dates.append(i)

    if missing_dates:
        locations = [f"location {i}" for i in missing_dates]
        flash(f"Missing dates for {', '.join(locations)}", "error")
        raise TravelValidationError("Missing required dates for travel entries")

    if len(geo) == len(location) == len(date):
        trips: list[Trip] = [
            Trip(location=geo_i, location_name=location_i, date=parse(date_i))
            for geo_i, location_i, date_i in zip(geo, location, date)
        ]

        if trips:
            markers = "|".join([trip.location[len("geo:") :] for trip in trips])
            map_url = f"https://maps.googleapis.com/maps/api/staticmap?&maptype=roadmap&size=500x500&markers=color:green|{markers}&path=color:green|weight:5|{markers}&key={GOOGLE_MAPS_KEY}"  # noqa: E501

            return Travel(
                trips=trips, map_data=requests.get(map_url).content, map_url=map_url
            )

    return Travel(trips=[])


def handle_event_data(request: Request) -> Optional[Event]:
    """Process event data from the form request."""
    app.logger.info(f"Event data: {request.form}")
    event_name = request.form.get("event_name")
    dt_start = request.form.get("dt_start")
    dt_end = request.form.get("dt_end")
    event_url = request.form.get("event_url")
    app.logger.info(f"Event data: {event_name}, {dt_start}, {dt_end}, {event_url}")
    if (
        event_name and dt_start
    ):  # Only create event if we have at least a name and start time
        return Event(
            event_name=event_name,
            dt_start=parse(dt_start) if dt_start else None,
            dt_end=parse(dt_end) if dt_end else None,
            url=HttpUrl(event_url) if event_url else None,
        )
    return None


def get_post_for_editing(file_path: str) -> Union[BlogPost, DraftPost]:
    """Get a post from the filesystem and prepare it for editing."""
    if not os.path.exists(f"{file_path}.json"):
        raise FileNotFoundError(f"Post not found at {file_path}.json")

    with open(f"{file_path}.json", "r") as f:
        data = json.load(f)

    for date_field in ["published", "updated", "dt_start", "dt_end"]:
        if data.get(date_field):
            try:
                data[date_field] = datetime.fromisoformat(data[date_field])
            except (ValueError, TypeError):
                data[date_field] = None

    if data.get("in_reply_to"):
        if isinstance(data["in_reply_to"], list):
            data["in_reply_to"] = [
                {"url": reply} if isinstance(reply, str) else reply
                for reply in data["in_reply_to"]
            ]

    try:
        return BlogPost(**data)
    except (ValidationError, ValueError):
        try:
            return DraftPost(**data)
        except ValidationError as e:
            raise ValueError(f"Invalid blog post data: {e}")


def syndicate_from_form(creation_request, data: BlogPost) -> None:
    """Using the data from a post just submitted, syndicate to social networks.
    Args:
        creation_request (Response): the response from an /add post form.
        data (dict): represents a new entry.
    """
    # Check to see if the post is in reply to another post and send a mention
    if not data.in_reply_to:
        return
    try:
        post_loc = "http://" + DOMAIN_NAME + data.url
        for reply in data.in_reply_to:
            requests.post(
                "https://fed.brid.gy/webmention",
                data={
                    "source": post_loc,
                    "target": reply,
                },
            )
    except TypeError as e:
        app.logger.error("Error mentioning: {0}. Error: {1}".format(reply, e))


def update_entry(
    update_request: Request,
    year: str,
    month: str,
    day: str,
    name: str,
    draft: bool = False,
) -> str:
    """Update an existing blog post"""
    try:
        file_name = f"{BLOG_STORAGE}/{year}/{month}/{day}/{name}"
        existing_entry = get_post_for_editing(file_name)
        updated_post = post_from_request(update_request, existing_entry)

        # Handle geo data if present
        if updated_post.geo and updated_post.geo.coordinates:
            # GeoLocation validation will handle coordinate validation
            if not updated_post.geo.name:
                # Only resolve name if not already provided
                lat, lon = updated_post.geo.coordinates
                location_info = resolve_placename(f"geo:{lat},{lon}")
                updated_post.geo.name = location_info.name
                updated_post.geo.location_id = location_info.geoname_id

        # Process markdown content
        updated_post.content = run(updated_post.content, f"{year}/{month}/{day}/")

        # Update the entry
        update_json_entry(updated_post, existing_entry, g=g.db, draft=draft)

        # Handle webmentions
        if isinstance(updated_post, BlogPost):
            syndicate_from_form(update_request, updated_post)

        return file_name

    except Exception as e:
        raise ValueError(f"Failed to update entry: {str(e)}")


def add_entry(creation_request: Request, draft: bool = False) -> str:
    """Add a new entry to the blog."""
    data = post_from_request(creation_request)

    # Convert Pydantic model to dictionary
    data_dict = data.model_dump()

    # Add required fields for new posts
    if not data_dict.get("published"):
        data_dict["published"] = datetime.now()
    if not data_dict.get("slug"):
        data_dict["slug"] = slugify(data_dict.get("title", str(uuid.uuid4())))
    if not data_dict.get("u_uid"):
        data_dict["u_uid"] = str(uuid.uuid4())
    if not data_dict.get("url"):
        data_dict["url"] = (
            f"/e/{data_dict['published'].strftime('%Y/%m/%d')}/{data_dict['slug']}"
        )

    # Handle location data if present
    if data_dict.get("location") and data_dict["location"].startswith("geo:"):
        location_info = resolve_placename(data_dict["location"])
        data_dict["location_name"] = location_info.name
        data_dict["location_id"] = location_info.geoname_id

    # Create the entry
    post = BlogPost(**data_dict)
    location = create_json_entry(post, g=g.db, draft=draft)

    # Handle webmentions if needed
    syndicate_from_form(creation_request, post)
    requests.post(
        "https://fed.brid.gy/webmention",
        data={
            "source": "https://" + DOMAIN_NAME + data_dict["url"],
            "target": "https://fed.brid.gy",
        },
    )
    return location


def action_stream_parser(filename):
    return NotImplementedError("this doesn't exist yet")


def search_by_tag(category):
    entries = []
    cur = g.db.execute(
        """
         SELECT entries.location FROM categories
         INNER JOIN entries ON
         entries.slug = categories.slug AND
         entries.published = categories.published
         WHERE categories.category='{category}'
         ORDER BY entries.published DESC
        """.format(
            category=category
        )
    )

    for (row,) in cur.fetchall():

        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))
    return entries


def load_activitypub_config():
    with open("config/activitypub.yml", "r") as f:
        config = yaml.safe_load(f)["activitypub"]

    return {
        "@context": config["context"],
        "type": "Person",
        "id": f"{config['bridgy_base']}/{config['domain']}",
        "name": config["profile"]["name"],
        "preferredUsername": config["profile"]["preferred_username"],
        "summary": config["profile"]["summary"],
        "inbox": f"{config['bridgy_base']}/{config['domain']}/inbox",
        "outbox": f"{config['bridgy_base']}/{config['domain']}/outbox",
        "followers": f"{config['bridgy_base']}/{config['domain']}/followers",
        "following": f"{config['bridgy_base']}/{config['domain']}/following",
    }


# Initialize once at startup
activitypub_profile = load_activitypub_config()


@app.route("/")
def show_entries():
    if request.headers.get("Accept") == "application/atom+xml":
        return show_atom()
    elif request.headers.get("Accept") == "application/as+json":
        return jsonify(activitypub_profile)

    # getting the entries we want to display.
    entries = []  # store the entries which will be presented
    cur = g.db.execute(  # grab in order of newest
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )

    for (row,) in cur.fetchall():  # iterate over the results
        if os.path.exists(row + ".json"):  # if the file fetched exists...
            # parse the json and add it to the list of entries.
            entries.append(file_parser_json(row + ".json"))
            if len(entries) == 10:
                break

    try:
        entries = entries[:10]  # get the 10 newest
    except IndexError:
        if len(entries) == 0:  # if there's an index error and the len is low..
            entries = None  # there are no entries
    # otherwise there are < 10 entries and we'll just display what we have ...
    before = 1  # holder which tells us which page we're on
    tags = get_most_popular_tags()[:10]

    display_articles = search_by_tag("article")[:3]

    return render_template(
        "blog_entries.html",
        entries=entries,
        before=before,
        popular_tags=tags[:10],
        display_articles=display_articles,
    )


@app.route("/rss.xml")
def show_rss():
    """The rss view: presents entries in rss form."""

    entries = []  # store the entries which will be presented
    cur = g.db.execute(  # grab in order of newest
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )
    updated = None
    for (row,) in cur.fetchall():  # iterate over the results
        # if the file fetched exists, append the parsed details
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))

    try:
        entries = entries[:10]  # get the 10 newest

    except IndexError:
        entries = None  # there are no entries

    template = render_template("rss.xml", entries=entries, updated=updated)
    response = make_response(template)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/atom.xml")
def show_atom():
    """The atom view: presents entries in atom form."""
    entries = []
    cur = g.db.execute(
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )
    updated = None
    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entry = file_parser_json(row + ".json")
            entries.append(entry)

    try:
        entries = entries[:10]
        # Access the published attribute directly from BlogPost object
        updated = entries[0].published if entries else None
        return Response(
            render_template("atom.xml", entries=entries, updated=updated),
            mimetype="application/atom+xml",
        )
    except (IndexError, AttributeError):
        return Response(
            render_template("atom.xml", entries=[], updated=None),
            mimetype="application/atom+xml",
        )


@app.route("/json.feed")
def show_json():
    """The rss view: presents entries in json feed form."""

    entries = []  # store the entries which will be presented
    cur = g.db.execute(  # grab in order of newest
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )

    for (row,) in cur.fetchall():  # iterate over the results
        # if the file fetched exists, append the parsed details
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))

    if len(entries) == 0:
        return jsonify({"message": "No entries found"}), 404

    entries = entries[:10]  # get the 10 newest
    feed_items = []

    for entry in entries:
        feed_item = {
            "id": entry["url"],
            "url": entry["url"],
            "content_text": entry["summary"] if entry["summary"] else entry["content"],
            "date_published": entry["published"],
            "author": {"name": "Alex Kearney"},
        }
        feed_items.append(feed_item)

    feed_json = {
        "version": "https://jsonfeed.org/version/1",
        "home_page_url": "https://kongaloosh.com/",
        "feed_url": "https://kongaloosh.com/json.feed",
        "title": "kongaloosh",
        "items": feed_items,
    }

    return jsonify(feed_json)


@app.route("/map")
def map():
    """"""
    geo_coords = []
    cur = g.db.execute(  # grab in order of newest
        """
        SELECT location
        FROM entries
        ORDER BY published DESC
        """
    )

    for (row,) in cur.fetchall():  # iterate over the results
        # if the file fetched exists, append the parsed details
        if os.path.exists(row + ".json"):
            entry = file_parser_json(row + ".json")
            if entry.location:
                geo_coords.append(entry.location[len("geo:") :].split(";")[0])

            if entry.travel:
                trips = entry.travel.trips
                if len(trips) > 0:  # if there's more than one location, make the map
                    geo_coords += [
                        destination.location[len("geo:") :] for destination in trips
                    ]

    return render_template("map.html", geo_coords=geo_coords, key=GOOGLE_MAPS_KEY)


@app.route("/page/<number>")
def pagination(number):
    """Gets the posts for a page number. Posts are grouped in 10s.
    Args:
        number: the page number we're currently on.
    """
    entries = get_entries_by_date()

    start = int(number) * 10  # beginning of page group is the page number * 10
    before = int(number) + 1  # increment the page group
    try:
        # get the next 10 entries starting at the page grouping
        entries = entries[start : start + 10]
    except IndexError:
        #  if there is an index error, it might be that there are
        #  fewer than 10 posts left...
        try:
            # try to get the remaining entries
            entries = entries[start : len(entries)]
        except IndexError:
            # if this still produces an index error,
            #  we are at the end and return no entries.
            entries = None
            before = 0  # set before so that we know we're at the end
    return render_template("blog_entries.html", entries=entries, before=before)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("page_not_found.html"), 404


@app.errorhandler(500)
def five_oh_oh(e):
    return render_template("server_error.html"), 500


@app.route("/add", methods=["GET", "POST"])
@require_auth
def add():
    """The form for user-submission"""
    if request.method == "GET":
        tags = get_most_popular_tags()[:10]
        return render_template(
            "edit_entry.html", entry=None, popular_tags=tags, type="add"
        )

    elif request.method == "POST":
        try:
            data = post_from_request(request)
            if "Save" in request.form:
                data = create_post_from_data(data)
                location = create_json_entry(data, g=g.db, draft=True)
                return redirect(location)
            else:
                return redirect(add_entry(request))
        except TravelValidationError:
            return redirect(url_for("add"))

    return "", 501


@app.route("/delete_draft/<name>", methods=["GET", "POST"])
def delete_drafts(name):
    """Deletes a given draft and associated files based on the name."""
    # todo: should have a 404 or something if the post doesn't actually exist.
    if not session.get("logged_in"):  # check permissions before deleting
        abort(401)
    # the file will be located in drafts under the slug name
    totalpath = os.path.join(DRAFT_STORAGE, name)
    # for all of the files associated with a post
    for extension in [".md", ".json", ".jpg"]:
        # if there's an associated file...
        if os.path.isfile(totalpath + extension):
            os.remove(totalpath + extension)  # ... delete it

    # note: because this is a draft, the images associated with the post will still be in the temp folder
    return redirect("/")


@app.route("/photo_stream", methods=["GET", "POST"])
def stream():
    """The form for user-submission"""
    if request.method == "GET":
        return render_template("photo_stream.html")

    elif request.method == "POST":  # if we're adding a new post
        if not session.get("logged_in"):
            abort(401)
    return "", 501


@app.route("/delete_entry/e/<year>/<month>/<day>/<name>", methods=["POST", "GET"])
def delete_entry(year, month, day, name):
    if not session.get("logged_in"):
        abort(401)
    else:
        app.logger.info(f"Deleting entry {year}/{month}/{day}/{name}")
        totalpath = f"{BLOG_STORAGE}/{year}/{month}/{day}/{name}"
        if not os.path.isfile(totalpath + ".json"):
            return redirect("/")
        entry = file_parser_json(totalpath + ".json")

        if isinstance(entry.photo, list):
            for photo in entry.photo:
                try:
                    os.remove(photo)
                except FileNotFoundError:
                    app.logger.error(
                        f"File not found at location {photo}; deletion did not occur."
                    )

        for extension in [".md", ".json", ".jpg"]:
            if os.path.isfile(totalpath + extension):
                os.remove(totalpath + extension)

        g.db.execute(
            """
            DELETE FROM ENTRIES
            WHERE Location=(?);
            """,
            (totalpath,),
        )
        g.db.commit()
        return redirect("/")
    return redirect("/", 500)


def rotate_image_by_exif(image: Image.Image) -> Image.Image:
    """Rotate image according to EXIF orientation tag"""
    try:
        # Find orientation tag
        orientation = next(
            (tag for tag, name in ExifTags.TAGS.items() if name == "Orientation"), None
        )

        if not orientation:
            return image

        exif = image.getexif()
        if not exif or orientation not in exif:
            return image

        # Rotate based on orientation value
        rotation_map = {3: 180, 6: 270, 8: 90}

        if rotation := rotation_map.get(exif[orientation]):
            return image.rotate(rotation, expand=True)

    except Exception as e:
        app.logger.error(f"Error processing EXIF orientation: {e}")

    return image


@app.route("/bulk_upload", methods=["GET", "POST"])
@require_auth
def bulk_upload():
    if request.method == "GET":
        return render_template("bulk_photo_uploader.html")
    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)

        temporary_file_name = datetime.now().strftime("%Y-%m-%d--%H-%M-%S")

        for uploaded_file in request.files.getlist("file"):
            i = 0
            assert uploaded_file.filename
            file_extension = uploaded_file.filename.split(".")[-1:][0]

            file_loc = os.path.join(
                BULK_UPLOAD_DIR,
                f"{temporary_file_name}.{file_extension}",
            )
            while os.path.exists(file_loc):
                file_loc = os.path.join(
                    BULK_UPLOAD_DIR,
                    f"{temporary_file_name}-{i}.{file_extension}",
                )
                i += 1

            image = Image.open(uploaded_file.stream)
            rotated_image = rotate_image_by_exif(image)
            rotated_image.save(file_loc)
        return redirect("/")
    else:
        return redirect("/404")


@app.route("/mobile_upload", methods=["GET", "POST"])
def mobile_upload():
    if request.method == "GET":
        return render_template("mobile_upload.html")
    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)

        file_path = BULK_UPLOAD_DIR
        for uploaded_file in request.files.getlist("files[]"):
            assert uploaded_file.filename
            app.logger.info("file " + uploaded_file.filename)
            file_loc = file_path + "{0}".format(uploaded_file.filename)

            # Check if it's a video file
            if uploaded_file.filename.lower().endswith(
                (".mp4", ".mov", ".qt", ".m4v", ".avi", ".wmv", ".flv", ".mkv")
            ):
                # Save the video file directly
                uploaded_file.save(file_loc)
            else:
                # Handle image with EXIF rotation as before
                try:
                    image = Image.open(uploaded_file.stream)

                    for orientation in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation] == "Orientation":
                            break

                    exif = dict(image.getexif().items())

                    if orientation in exif:
                        if exif[orientation] == 3:
                            image = image.rotate(180, expand=True)
                        elif exif[orientation] == 6:
                            image = image.rotate(270, expand=True)
                        elif exif[orientation] == 8:
                            image = image.rotate(90, expand=True)

                    image.save(file_loc)
                except Exception as e:
                    app.logger.error(
                        f"Error processing image {uploaded_file.filename}: {str(e)}"
                    )
                    # Save the original file if image processing fails
                    uploaded_file.save(file_loc)

        return redirect("/")
    else:
        return redirect("/404")


@app.route("/md_to_html", methods=["POST"])
def md_to_html():
    try:
        app.logger.debug(f"Request headers: {dict(request.headers)}")
        app.logger.debug(f"Request data: {request.get_data()}")

        if not request.is_json:
            app.logger.error(f"Invalid content type: {request.content_type}")
            return (
                jsonify({"error": f"Request must be JSON, got {request.content_type}"}),
                400,
            )

        data = request.get_json()
        app.logger.debug(f"Parsed JSON data: {data}")

        if not data or "text" not in data:
            app.logger.error("Missing text in request data")
            return jsonify({"error": "No text provided in request"}), 400

        # Your existing markdown conversion logic
        md = markdown.Markdown(
            extensions=["extra", HashtagExtension(), AlbumExtension()]
        )
        html = md.convert(data["text"])

        response = jsonify({"html": html})
        # Set CSRF token in response
        response.headers["X-CSRF-Token"] = generate_csrf()
        return response

    except Exception as e:
        app.logger.error(f"Error processing markdown: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/geonames/<query>", methods=["GET"])
def geonames_wrapper(query):
    if request.method == "GET":
        print(f"Received geonames search request for: {query}")
        try:
            url = f"http://api.geonames.org/searchJSON?q={query}&maxRows=10&username={GEONAMES}"
            print(f"Calling geonames API: {url}")
            resp = requests.get(url)
            print(f"Geonames response status: {resp.status_code}")
            results = resp.json()
            print(f"Geonames raw response: {results}")

            if "geonames" in results:
                results["geonames"] = [
                    {
                        "title": f"{place['name']}, {place.get('adminName1', '')}, {place['countryName']}",
                        "lat": place["lat"],
                        "lng": place["lng"],
                    }
                    for place in results["geonames"]
                ]
                print(f"Transformed response: {results}")

            response = jsonify(results)
            return response
        except Exception as e:
            print(f"Error in geonames_wrapper: {str(e)}")
            return jsonify({"error": str(e)}), 500
    return redirect("/404"), 404


@app.route("/recent_uploads", methods=["GET", "POST"])
def recent_uploads():
    """Return a formatted list of all images in the current day's directory."""
    if request.method == "GET":
        directory = BULK_UPLOAD_DIR
        insert_pattern = "%s" if request.args.get("stream") else "[](%s)"

        # Define allowed image extensions
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

        file_list = [
            os.path.join(BULK_UPLOAD_DIR, file)
            for file in os.listdir(directory)
            if os.path.splitext(file.lower())[1] in IMAGE_EXTENSIONS
        ]

        rows = []
        for i in range(0, len(file_list), 3):
            row_images = file_list[i : i + 3]
            row = "".join(
                [
                    f"""
                <a class="p-2 text-center" onclick="insertAtCaret('text_input','{insert_pattern % image}', 'img_{j}');return false;">
                    <img src="/{image}" id="img_{j}" class="img-fluid" style="max-height:200px; width:auto;">
                </a>
                """
                    for j, image in enumerate(row_images, start=i)
                ]
            )
            rows.append(f'<div class="d-flex flex-row">{row}</div>')

        return "\n".join(rows)

    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)
        try:
            to_delete = json.loads(request.get_data())["to_delete"]
            file_path = PERMANENT_PHOTOS_DIR + to_delete[len("/images/") :]
            if os.path.isfile(file_path):
                os.remove(file_path)
                return "deleted"
            return "file not found", 404
        except KeyError as e:
            app.logger.error(f"KeyError: {e}")
            abort(400)

    abort(405)  # Method Not Allowed


@app.route("/edit/e/<year>/<month>/<day>/<name>", methods=["GET", "POST"])
@require_auth
def edit(year, month, day, name):
    """The form for user-submission"""
    if request.method == "GET":
        file_name = f"{BLOG_STORAGE}/{year}/{month}/{day}/{name}"
        entry = get_post_for_editing(file_name)
        return render_template("edit_entry.html", type="edit", entry=entry)
    elif request.method == "POST":
        if "Submit" in request.form:
            # video and photo logging
            app.logger.info(f"Existing photos: {request.form.get('existing_photos')}")
            app.logger.info(f"New photos: {request.form.get('new_photos')}")
            app.logger.info(f"Existing videos: {request.form.get('existing_videos')}")
            app.logger.info(f"New videos: {request.form.get('new_videos')}")
            update_entry(request, year, month, day, name)
        return redirect("/")

    return "", 405  # Method Not Allowed


@app.route("/e/<year>/<month>/<day>/<name>")
def profile(year, month, day, name):
    """Get a specific article"""

    file_name = f"{BLOG_STORAGE}/{year}/{month}/{day}/{name}"
    # if someone else is consuming
    if request.headers.get("Accept") == "application/json":
        return jsonify(file_parser_json(file_name + ".json"))

    entry = file_parser_json(file_name + ".json")

    mentions, likes, reposts = get_mentions(
        "https://"
        + DOMAIN_NAME
        + "/e/{year}/{month}/{day}/{name}".format(
            year=year, month=month, day=day, name=name
        )
    )

    return render_template(
        "entry.html", entry=entry, mentions=mentions, likes=likes, reposts=reposts
    )


@app.route("/t/<category>")
def tag_search(category):
    """Get all entries with a specific tag"""
    if request.headers.get("Accept") == "application/json":
        entries = []
        query = """SELECT entries.location
         FROM categories
         INNER JOIN entries ON
         entries.slug = categories.slug AND
         entries.published = categories.published
         WHERE categories.category='{category}'""".format(
            category=category
        )
        args = request.args
        for key in args.keys():
            strf = key[0] if key[0] != "y" else "Y"
            query += (
                "\nand CAST(strftime('%{0}', entries.published)AS INT) = {1}".format(
                    strf, args.get(key)
                )  # noqa: E501
            )
        query += "\nORDER BY entries.published DESC"
        cur = g.db.execute(query)
        for (row,) in cur.fetchall():
            if os.path.exists(row + ".json"):
                entries.append(file_parser_json(row + ".json"))
        return jsonify(entries)
    entries = search_by_tag(category)
    return render_template("blog_entries.html", entries=entries)


@app.route("/t/")
def all_tags():
    "Get all tags and order them in descending quantity."
    cur = g.db.execute(
        """
        select category, count(category) as count
        from categories
        group by category
        order by count(category) desc
        """
    )
    tags = cur.fetchall()

    if request.headers.get("Accept") == "application/json":
        return jsonify(tags)

    return render_template("tags.html", tags=tags)


@app.route("/e/<year>/")
def time_search_year(year):
    """Gets all entries posted during a specific year"""
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        WHERE CAST(strftime('%Y',entries.published)AS INT) = {year}
        ORDER BY entries.published DESC
        """.format(
            year=int(year)
        )
    )

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))

    if request.headers.get("Accept") == "application/json":
        return jsonify(entries)

    return render_template("blog_entries.html", entries=entries)


@app.route("/e/<year>/<month>/")
def time_search_month(year, month):
    """Gets all entries posted during a specific month"""
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        WHERE CAST(strftime('%Y',entries.published)AS INT) = {year}
        AND CAST(strftime('%m',entries.published)AS INT) = {month}
        ORDER BY entries.published DESC
        """.format(
            year=int(year), month=int(month)
        )
    )

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))

    if request.headers.get("Accept") == "application/json":
        return jsonify(entries)

    return render_template("blog_entries.html", entries=entries)


@app.route("/e/<year>/<month>/<day>/")
def time_search(year, month, day):
    """Gets all notes posted on a specific day"""
    entries = []
    cur = g.db.execute(
        """
        SELECT entries.location FROM entries
        WHERE CAST(strftime('%Y',entries.published)AS INT) = {year}
        AND CAST(strftime('%m',entries.published)AS INT) = {month}
        AND CAST(strftime('%d',entries.published)AS INT) = {day}
        ORDER BY entries.published DESC
        """.format(
            year=int(year), month=int(month), day=int(day)
        )
    )

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))

    if request.headers.get("Accept") == "application/json":
        return jsonify(entries)

    return render_template("blog_entries.html", entries=entries)


@app.route("/a/")
def articles():
    """Gets all the articles"""
    entries = []
    cur = g.db.execute(
        """
         SELECT entries.location FROM categories
         INNER JOIN entries ON
         entries.slug = categories.slug AND
         entries.published = categories.published
         WHERE categories.category='{category}'
         ORDER BY entries.published DESC
        """.format(
            category="article"
        )
    )

    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))

    if request.headers.get("Accept") == "application/json":
        return jsonify(entries)

    return render_template("blog_entries.html", entries=entries)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form["username"] != app.config["USERNAME"]:
            flash("Invalid credentials")
            error = "Invalid username"
        elif request.form["password"] != app.config["PASSWORD"]:
            flash("Invalid credentials")
            error = "Invalid password"
        else:
            flash("You were successfully logged in")
            session["logged_in"] = True
            return redirect("/")
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    flash("You were logged out")
    return redirect(url_for("show_entries"))


# TODO: the POST functionality could 100% just be the same as our add function
@app.route("/micropub", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
def handle_micropub():
    return "", 501


@app.route("/list_mentions")
def print_mentions():
    r = requests.get(
        f"https://webmention.io/api/mentions?target={DOMAIN_NAME}",
        headers={"Accept": "application/json"},
    ).json()["links"]
    return render_template("mentions.html", mentions=r)


@app.route("/inbox", methods=["GET", "POST", "OPTIONS"])
def handle_inbox():
    if request.method == "GET":
        inbox_location = "inbox/"
        entries = [f for f in os.listdir(inbox_location) if f.endswith(".json")]
        for_approval = [e for e in entries if e.startswith("approval_")]
        entries = [e for e in entries if not e.startswith("approval_")]

        if "text/html" in request.headers.get("Accept", ""):
            return render_template(
                "inbox.html", entries=entries, for_approval=for_approval
            )
        elif "application/ld+json" in request.headers.get("Accept", ""):
            inbox_items = {
                "@context": "https://www.w3.org/ns/ldp",
                "@id": f"http://{DOMAIN_NAME}/inbox",
                "http://www.w3.org/ns/ldp#contains": [
                    {"@id": f"http://{DOMAIN_NAME}/inbox/{entry}"} for entry in entries
                ],
            }
            return jsonify(inbox_items), 200
        else:
            return "", 501

    elif request.method == "POST":
        data = request.json
        assert data
        sender = (
            data.get("actor", {}).get("@id")
            or data.get("actor", {}).get("id")
            or data.get("actor")
        )

        if sender in ["https://rhiaro.co.uk", "https://rhiaro.co.uk/#me"]:
            location = f"inbox/{slugify.slugify(str(datetime.now()))}.json"
            with open(location, "w") as f:
                json.dump(data, f)
            return "", 201, {"Location": location}
        else:
            try:
                if data and "context" in data:
                    location = (
                        f"inbox/approval_{slugify.slugify(str(datetime.now()))}.json"
                    )
                    with open(location, "w") as f:
                        json.dump(data, f)
                    return (
                        jsonify({"@id": "", "http://www.w3.org/ns/ldp#contains": []}),
                        202,
                    )
                else:
                    return "", 403
            except requests.ConnectionError:
                return "", 403

    return "", 501


@app.route("/inbox/send/", methods=["GET", "POST"])
def notifier():
    return "method not allowed", 501


# TODO: verify this still works
@app.route("/inbox/<name>", methods=["GET"])
def show_inbox_item(name):
    entry = json.loads(open("inbox/" + name).read())

    if request.headers.get("Accept") == "application/ld+json":
        return jsonify(entry), 200

    if "text/html" in request.headers.get("Accept", ""):
        sender = (
            entry.get("actor", {}).get("@id")
            or entry.get("actor", {}).get("id")
            or entry.get("actor")
            or entry.get("@id")
        )
        return render_template("inbox_notification.html", entry=entry, sender=sender)

    return jsonify(entry), 200


@app.route("/drafts", methods=["GET"])
@require_auth
def show_drafts():
    if not session.get("logged_in"):
        abort(401)
    entries = [
        file_parser_json(os.path.join(DRAFT_STORAGE, f))
        for f in os.listdir(DRAFT_STORAGE)
        if f.endswith(".json")
    ]
    return render_template("drafts_list.html", entries=entries)


@app.route("/drafts/<name>", methods=["GET", "POST"])
@require_auth
def show_draft(name):
    if not session.get("logged_in"):
        abort(401)
    if request.method == "GET":
        draft_location = os.path.join(DRAFT_STORAGE, name)
        entry = get_post_for_editing(draft_location)
        return render_template("edit_entry.html", entry=entry, type="draft")

    if request.method == "POST":
        draft_file = os.path.join(DRAFT_STORAGE, f"{name}.json")
        if os.path.exists(draft_file):
            existing_data = file_parser_json(draft_file)
        else:
            abort(404)

        form_data = post_from_request(request)

        if "Save" in request.form:
            update_json_entry(form_data, existing_data, g=g, draft=True)
            return redirect("/drafts")

        if "Submit" in request.form:
            # Convert both to dicts before merging
            merged_data = {**form_data.model_dump(), **existing_data.model_dump()}
            post = BlogPost(**merged_data)
            location = create_json_entry(post, g=g.db, draft=False)
            os.remove(draft_file)
            return redirect(location)
    abort(405)


# TODO not sure if these specs still work
@app.route("/ap_subscribe", methods=["POST"])
def subscribe_request():
    if request.method == "POST":
        social_name = request.form["handle"]
        user_name, social_domain = social_name.split("@")
        response = requests.get(
            "https://"
            + social_domain
            + "/.well-known/webfinger/?resource=acct:"
            + social_name
        )
        links = response.json()["links"]
        for link in links:
            if link["rel"] == "http://ostatus.org/schema/1.0/subscribe":
                return redirect(
                    link["template"].format(uri="@kongaloosh.com@kongaloosh.com")
                )
    return "", 501


@app.route("/ap_follow", methods=["POST"])
def follow_request():
    if not session.get("logged_in"):  # check permissions before deleting
        abort(401)
    if request.method == "POST":
        social_name = request.form["handle"]
        user_name, social_domain = social_name.split("@")
        url = "https://" + social_domain + "/@" + user_name
        data = json.load(open("followers.json"))
        data["following"].append({"actor": social_name, "url": url})
        with open("followers.json", "w") as jsonf:
            jsonf.write(json.dumps(data))

        requests.post(
            "https://fed.brid.gy/webmention",
            data={
                "target": "https//fed.brigy.gy",
                "source": "https://kongaloosh.com/following/" + social_name,
            },
        )
    return redirect("/following/" + social_name)


@app.route("/notification", methods=["GET", "POST"])
def notification():
    return jsonify({"message": "This feature is not implemented yet"}), 501


# TODO: we're using brid.gy now, we can probably remove these


@app.route("/followers", methods=["GET"])
def follower_list():
    followers = json.load(open("followers.json"))
    return render_template("followers.html", followers=followers["following"])


@app.route("/following/<account>", methods=["GET"])
def follower_individual(account):
    followers = json.load(open("followers.json"))
    for actor in followers["following"]:
        if actor["actor"] == account:
            return render_template("follower.html", follower=actor)

    return redirect("/404")


@app.route("/already_made", methods=["GET"])
def post_already_exists():
    return render_template("already_exists.html")


@app.after_request  # This decorator runs this function after every request
def add_security_headers(response: Union[Response, str]) -> Response:
    """Add security headers to the response"""
    # Convert string responses to Response objects if needed
    if not isinstance(response, Response):
        response = Response(response)

    # Content Security Policy (CSP) - The main security control
    response.headers["Content-Security-Policy"] = (
        # default-src: Fallback for other resource types
        "default-src 'self'; "
        # script-src: Controls what JavaScript can run
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://code.jquery.com "
        "https://cdnjs.cloudflare.com "
        "https://maxcdn.bootstrapcdn.com "
        "https://cdn.jsdelivr.net "
        "https://webmention.io "
        "https://ajax.googleapis.com "
        "https://www.google-analytics.com "
        "http://www.google-analytics.com "
        "https://www.googletagmanager.com "
        "https://nominatim.openstreetmap.org "
        "https://brid.gy https://fed.brid.gy; "
        # style-src: Controls CSS sources
        "style-src 'self' 'unsafe-inline' "
        "https://maxcdn.bootstrapcdn.com "
        "https://fonts.googleapis.com "
        "https://cdn.jsdelivr.net; "
        # font-src: Controls font loading
        "font-src 'self' https://fonts.gstatic.com https://maxcdn.bootstrapcdn.com; "
        # connect-src: Controls AJAX, WebSocket, etc
        "connect-src 'self' https://webmention.io https://www.google-analytics.com "
        "https://nominatim.openstreetmap.org "
        "https://brid.gy https://fed.brid.gy; "
        # img-src: Controls image sources
        "img-src 'self' data: blob: https: https://www.google-analytics.com; "
        # media-src: Controls video/audio
        "media-src 'self' blob: data:; "
    )

    # Additional security headers
    response.headers["X-Frame-Options"] = "SAMEORIGIN"  # Prevents clickjacking
    response.headers["X-Content-Type-Options"] = (
        "nosniff"  # Prevents MIME-type sniffing
    )
    response.headers["X-XSS-Protection"] = "1; mode=block"  # Browser XSS protection
    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"  # Controls referrer info
    )

    return response


# Apply headers to all responses
app.after_request(add_security_headers)

if __name__ == "__main__":
    app.run(debug=True)
