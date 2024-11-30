#!/usr/bin/python
# coding: utf-8
import configparser
import json
from typing import List, Optional, Union
import markdown
import os
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
    Response,
    make_response,
    jsonify,
    Blueprint,
)
from werkzeug.datastructures import FileStorage
from jinja2 import Environment
from pysrc.markdown_hashtags.markdown_hashtag_extension import HashtagExtension
from pysrc.markdown_albums.markdown_album_extension import AlbumExtension
from pysrc.post import BlogPost, Event, PlaceInfo, Travel, Trip, DraftPost
from pysrc.python_webmention.mentioner import get_mentions
from slugify import slugify
from pysrc.authentication.indieauth import checkAccessToken
from pysrc.file_management.file_parser import (
    create_json_entry,
    update_json_entry,
    file_parser_json,
)
from pysrc.file_management.markdown_album_pre_process import run
from pysrc.file_management.markdown_album_pre_process import new_prefix
from dataclasses import dataclass
import uuid
from werkzeug.utils import secure_filename

jinja_env = Environment()

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
ORIGINAL_PHOTOS_DIR = config.get("PhotoLocations", "BulkUploadLocation")
# the url to use for showing recent bulk uploads
BLOG_STORAGE = config.get("PhotoLocations", "BlogStorage")
BULK_UPLOAD_DIR = config.get("PhotoLocations", "BulkUploadLocation")

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config["STATIC_FOLDER"] = os.getcwd()

# Add a second static folder specifically for serving photos
photos_path = os.path.join(os.getcwd(), BLOG_STORAGE)
photos = Blueprint(
    "blog_data_storage",
    __name__,
    static_url_path=f"/{BLOG_STORAGE}",
    static_folder=photos_path,
)
app.register_blueprint(photos)
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
    cur = g.db.execute(
        """SELECT entries.location FROM entries
        ORDER BY entries.published DESC
        """
    )
    for (row,) in cur.fetchall():
        if os.path.exists(row + ".json"):
            entries.append(file_parser_json(row + ".json"))
    return entries


def get_most_popular_tags() -> List[str]:
    """Get tags in descending order of usage, excluding post type declarations.

    Returns:
        List of tags in descending order by usage.
    """
    cur = g.db.execute(
        """
        SELECT category, COUNT(*) as count
        FROM categories
        WHERE category NOT IN ('None', 'image', 'album', 'bookmark', 'note')
        GROUP BY category
        ORDER BY count DESC
        """
    )
    return [row[0] for row in cur.fetchall()]


def resolve_placename(location: str) -> PlaceInfo:
    """
    Given a location, returns the closest placename and geoid of a location.
    Args:
        location (str): the geocoords of some location in the format 'geo:lat,long'
    Returns:
        Optional[PlaceInfo]: the placename info of the resolved place, or None if not found
    """
    try:
        lat, long = location[4:].split(",")
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
    location: Optional[str] = None
    event: Optional[Event] = None
    travel: Optional[Travel] = None
    photo: Optional[List[str]] = None  # Stores existing photo paths


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
        data.photo = [p.strip() for p in photo_list.split(",")]

    return data


def handle_uploaded_files(request: Request) -> List[str]:
    """Process only the file uploads from the request"""
    photo_paths = []
    # Ensure uploads directory exists
    upload_dir = os.path.join(os.getcwd(), BULK_UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)

    if files := request.files.getlist("photo_file[]"):
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                path = os.path.join(upload_dir, filename)
                file.save(path)
                photo_paths.append(os.path.join(BULK_UPLOAD_DIR, filename))

    return photo_paths


def post_from_request(
    request: Request, existing_post: Optional[BlogPost] = None
) -> Union[DraftPost, BlogPost]:
    """Process form data into a Post model based on the form action (Save vs Submit)"""
    try:
        # Get form data
        form_data = process_form_data(request)
        uploaded_photos = handle_uploaded_files(request)

        # Handle travel data
        travel_data = None
        if "geo[]" in request.form:
            travel_data = handle_travel_data(request)

        # Combine existing photos with new uploads
        all_photos = (form_data.photo or []) + uploaded_photos

        # Base post data suitable for both drafts and published posts
        post_data = {
            "title": form_data.title,
            "content": form_data.content,
            "summary": form_data.summary,
            "category": form_data.category,
            "photo": all_photos if all_photos else None,
            "in_reply_to": form_data.in_reply_to,
            "travel": travel_data,
        }

        # If this is a Save action OR it's a new post (not existing)
        if "Save" in request.form or not existing_post:
            # For existing posts being saved, preserve metadata
            if existing_post and "Save" in request.form:
                post_data.update(
                    {
                        "slug": existing_post.slug,
                        "u_uid": existing_post.u_uid,
                        "url": existing_post.url,
                        "published": existing_post.published,
                    }
                )
            return DraftPost(**post_data)

        # Only return BlogPost for explicit Submit actions on existing posts
        post_data.update(
            {
                "published": form_data.published or datetime.now(),
                "slug": existing_post.slug,
                "u_uid": existing_post.u_uid,
                "url": existing_post.url,
            }
        )

        return BlogPost(**post_data)

    except Exception as e:
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


def handle_travel_data(request: Request) -> Travel:
    geo = request.form.getlist("geo[]")
    location = request.form.getlist("location[]")
    date = request.form.getlist("date[]")

    if len(geo) == len(location) == len(date):
        trips: list[Trip] = [
            Trip(location=g, location_name=l, date=parse(d))
            for g, l, d in zip(geo, location, date)
        ]

        if trips:
            markers = "|".join([trip.location[len("geo:") :] for trip in trips])
            map_url = f"https://maps.googleapis.com/maps/api/staticmap?&maptype=roadmap&size=500x500&markers=color:green|{markers}&path=color:green|weight:5|{markers}&key={GOOGLE_MAPS_KEY}"

            return Travel(
                trips=trips, map_data=requests.get(map_url).content, map_url=map_url
            )

    return Travel(trips=[])


def handle_event_data(request: Request) -> Event:
    event_data = {}
    for key in ["dt_start", "dt_end", "event_name"]:
        value = request.form.get(key)
        if value:
            event_data[key] = (
                datetime.date.parse(value) if key.startswith("dt_") else value
            )
        else:
            return Event()
    return Event(**event_data)


def get_post_for_editing(file_path: str) -> BlogPost:
    """Get a post from the filesystem and prepare it for editing.

    Args:
        file_path: Path to the JSON file containing the post data

    Returns:
        BlogPost: The post data ready for editing

    Raises:
        FileNotFoundError: If the post file doesn't exist
    """
    if not os.path.exists(f"{file_path}.json"):
        raise FileNotFoundError(f"Post not found at {file_path}.json")

    # Load the post data
    with open(f"{file_path}.json", "r") as f:
        data = json.load(f)

    # Convert in_reply_to list to comma-separated string for form
    if data.get("in_reply_to"):
        if isinstance(data["in_reply_to"], list):
            data["in_reply_to"] = ", ".join(
                [
                    reply["url"] if isinstance(reply, dict) else reply
                    for reply in data["in_reply_to"]
                ]
            )

    # Parse dates back to datetime objects
    for date_field in ["published", "updated", "dt_start", "dt_end"]:
        if data.get(date_field):
            try:
                data[date_field] = datetime.fromisoformat(data[date_field])
            except (ValueError, TypeError):
                data[date_field] = None

    try:
        return BlogPost(**data)
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
        # Get the updated post data
        file_name = f"{BLOG_STORAGE}/{year}/{month}/{day}/{name}"
        existing_entry = get_post_for_editing(file_name)

        updated_post = post_from_request(update_request, existing_entry)

        # Handle location data if present
        if updated_post.location and updated_post.location.startswith("geo:"):
            location_info = resolve_placename(updated_post.location)
            updated_post.location_name = location_info.name
            updated_post.location_id = location_info.geoname_id

        # Process markdown content
        updated_post.content = run(updated_post.content, date=updated_post.published)

        # Update the entry
        update_json_entry(updated_post, existing_entry, g=g.db, draft=draft)

        # Handle webmentions
        syndicate_from_form(update_request, updated_post)

        return file_name

    except Exception as e:
        app.logger.error(f"Error updating entry: {e}")
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


@app.route("/")
def show_entries():
    """The main view: presents author info and entries."""
    if request.headers.get("Accept") == "application/atom+xml":
        return show_atom()
    elif request.headers.get("Accept") == "application/as+json":
        # TODO: this shouldn't be hard-coded. Pull this from the config.
        moi = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Person",
            "id": "https://fed.brid.gy/kongaloosh.com",
            "name": "Alex Kearney",
            "preferredUsername": "Kongaloosh",
            "summary": "Hi, I'm a PhD candidate focused on Artificial Intelligence and Reinforcement Learning. I'm supervised by Rich Sutton and Patrick Pilarski at the University of Alberta in the Reinforcement Learning & Artificial Intelligence Lab.\n My research addresses how artificial intelligence systems can construct knowledge by deciding both what to learn and how to learn, independent of designer instruction. I predominantly use Reinforcement Learning methods.",
            "inbox": "https://fed.brid.gy/kongaloosh.com/inbox",
            "outbox": "https://fed.brid.gy/kongaloosh.com/outbox",
            "followers": "https://fed.brid.gy/kongaloosh.com/followers",
            "following": "https://fed.brid.gy/kongaloosh.com/following",
        }
        return jsonify(moi)

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


@app.route("/webfinger")
def finger():
    return jsonify(json.loads(open("webfinger.json", "r").read()))


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
        updated = entries[0]["published"]
    except IndexError:
        entries = None  # there are no entries

    template = render_template("atom.xml", entries=entries, updated=updated)
    response = make_response(template)
    response.headers["Content-Type"] = "application/atom+xml"
    return response


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
        #  if there is an index error, it might be that there are fewer than 10 posts left...
        try:
            # try to get the remaining entries
            entries = entries[start : len(entries)]
        except IndexError:
            # if this still produces an index error, we are at the end and return no entries.
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
def add():
    """The form for user-submission"""
    if request.method == "GET":
        tags = get_most_popular_tags()[:10]
        return render_template(
            "edit_entry.html", entry=None, popular_tags=tags, type="add"
        )

    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)

        if "Submit" in request.form:
            return redirect(add_entry(request))

        elif "Save" in request.form:  # if we're simply saving the post as a draft
            data = post_from_request(request)
            return redirect(create_json_entry(data, g=g, draft=True))

    return "", 501


@app.route("/delete_draft/<name>", methods=["GET"])
def delete_drafts():
    """Deletes a given draft and associated files based on the name."""
    # todo: should have a 404 or something if the post doesn't actually exist.
    if not session.get("logged_in"):  # check permissions before deleting
        abort(401)
    # the file will be located in drafts under the slug name
    totalpath = "drafts/{name}"
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


@app.route("/bulk_upload", methods=["GET", "POST"])
def bulk_upload():
    if request.method == "GET":
        return render_template("bulk_photo_uploader.html")
    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)

        file_path = ORIGINAL_PHOTOS_DIR

        app.logger.info("uploading at " + file_path)
        app.logger.info(request.files)
        for uploaded_file in request.files.getlist("file"):
            i = 0
            file_loc = (
                file_path
                + datetime.now().strftime("%Y-%m-%d--%H-%M-%S")
                + "."
                + uploaded_file.filename.split(".")[-1:][0]
            )
            while os.path.exists(file_loc):
                file_loc = (
                    file_path
                    + datetime.now().strftime("%Y-%m-%d--%H-%M-%S-")
                    + str(i)
                    + "."
                    + uploaded_file.filename.split(".")[-1:][0]
                )
                i += 1

            image = Image.open(uploaded_file)
            try:
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == "Orientation":
                        break
                exif = dict(image._getexif().items())
                try:
                    if exif[orientation] == 3:
                        image = image.rotate(180, expand=True)
                    elif exif[orientation] == 6:
                        image = image.rotate(270, expand=True)
                    elif exif[orientation] == 8:
                        image = image.rotate(90, expand=True)
                except KeyError:
                    app.logger.error(
                        "exif orientation key error: key was {0}, not in keys {1}".format(
                            orientation, exif.keys()
                        )
                    )
            except AttributeError:
                # could be a png or something without exif
                pass
            app.logger.info("saved at " + file_loc)
            image.save(file_loc)
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

        file_path = ORIGINAL_PHOTOS_DIR
        for uploaded_file in request.files.getlist("files[]"):
            assert uploaded_file.filename
            app.logger.info("file " + uploaded_file.filename)
            file_loc = file_path + "{0}".format(uploaded_file.filename)
            image = Image.open(uploaded_file.stream)

            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == "Orientation":
                    break

            exif = dict(image.getexif().items())

            if exif[orientation] == 3:
                image = image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image = image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image = image.rotate(90, expand=True)

            image.save(file_loc)
        return redirect("/")
    else:
        return redirect("/404")


@app.route("/md_to_html", methods=["POST"])
def md_to_html():
    """
    :returns mar
    """
    if request.method == "POST":
        return jsonify(
            {
                "html": markdown.markdown(
                    request.data.decode("utf-8"),
                    extensions=[
                        "fenced_code",
                        "mdx_math",
                        AlbumExtension(),
                        HashtagExtension(),
                    ],
                )
            }
        )

    else:
        return redirect("/404"), 404


@app.route("/geonames/<query>", methods=["GET"])
def geonames_wrapper(query):
    if request.method == "GET":
        resp = requests.get(
            f"http://api.geonames.org/wikipediaSearchJSON?username=kongaloosh&q={query}"
        )
        response = jsonify(resp.json())
        response.status_code = resp.status_code
        response.headers.extend(resp.headers)
        return response
    else:
        return redirect("/404"), 404


@app.route("/recent_uploads", methods=["GET", "POST"])
def recent_uploads():
    """Return a formatted list of all images in the current day's directory."""
    if request.method == "GET":
        directory = ORIGINAL_PHOTOS_DIR
        insert_pattern = "%s" if request.args.get("stream") else "[](%s)"

        file_list = [PHOTOS_URL + file for file in os.listdir(directory)]

        rows = []
        for i in range(0, len(file_list), 3):
            row_images = file_list[i : i + 3]
            row = "".join(
                [
                    f"""
                <a class="p-2 text-center" onclick="insertAtCaret('text_input','{insert_pattern % image}', 'img_{j}');return false;">
                    <img src="{image}" id="img_{j}" class="img-fluid" style="max-height:auto; width:25%;">
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
            file_path = new_prefix + to_delete[len("/images/") :]
            if os.path.isfile(file_path):
                os.remove(file_path)
                return "deleted"
            return "file not found", 404
        except KeyError:
            abort(400)

    abort(405)  # Method Not Allowed


@app.route("/edit/e/<year>/<month>/<day>/<name>", methods=["GET", "POST"])
def edit(year, month, day, name):
    """The form for user-submission"""
    if request.method == "GET":
        file_name = f"{BLOG_STORAGE}/{year}/{month}/{day}/{name}"
        entry = get_post_for_editing(file_name)
        return render_template("edit_entry.html", type="edit", entry=entry)
    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)
        if "Submit" in request.form:
            update_entry(request, year, month, day, name)
        return redirect("/")
    # Add a default return statement
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
                )
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
    """Get all entries with a specific tag"""

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
    app.logger.info("handleMicroPub [%s]" % request.method)
    if request.method == "POST":  # if post, authorise and create
        access_token = request.headers.get(
            "Authorization"
        )  # get the token and report it
        app.logger.info("token [%s]" % access_token)
        if access_token:  # if the token is not none...
            access_token = access_token.replace("Bearer ", "")
            app.logger.info("acccess [%s]" % request)
            # if the token is valid ...
            if checkAccessToken(access_token, request.form.get("client_id.data")):
                app.logger.info("authed")
                app.logger.info(request.data)
                app.logger.info(request.form.keys())
                app.logger.info(request.files)
                data = {
                    "h": None,
                    "title": None,
                    "summary": None,
                    "content": None,
                    "published": None,
                    "updated": None,
                    "category": None,
                    "slug": None,
                    "location": None,
                    "location_name": None,
                    "location_id": None,
                    "in_reply_to": None,
                    "repost-of": None,
                    "syndication": None,
                    "photo": None,
                }

                for key in (
                    "name",
                    "summary",
                    "content",
                    "published",
                    "updated",
                    "category",
                    "slug",
                    "location",
                    "place_name",
                    "in_reply_to",
                    "repost-of",
                    "syndication",
                    "syndicate-to[]",
                ):
                    try:
                        data[key] = request.form.get(key)
                    except KeyError:
                        pass

                cat = request.form.get("category[]")
                if cat:
                    data["category"] = cat

                if type(data["category"]) is unicode:
                    data["category"] = [
                        i.strip() for i in data["category"].lower().split(",")
                    ]
                elif type(data["category"]) is list:
                    data["category"] = data["category"]
                elif data["category"] is None:
                    data["category"] = []

                if not data["published"]:  # if we don't have a timestamp, make one now
                    data["published"] = datetime.today()
                else:
                    data["published"] = parse(data["published"])

                for key, name in [
                    ("photo", "image"),
                    ("audio", "audio"),
                    ("video", "video"),
                ]:
                    try:
                        if request.files.get(key):
                            img = request.files.get(key)
                            data[key] = img
                            # we've added an image, so append it
                            data["category"].append(name)
                    except KeyError:
                        pass

                if data["location"] is not None and data["location"].startswith("geo:"):
                    if data["place_name"]:
                        data["location_name"] = data["place_name"]
                    elif data["location"].startswith("geo:"):
                        (place_name, geo_id) = resolve_placename(data["location"])
                        data["location_name"] = place_name
                        data["location_id"] = geo_id

                location = create_json_entry(data, g=g)

                resp = Response(
                    status="created",
                    headers={"Location": "http://" + DOMAIN_NAME + location},
                )
                resp.status_code = 201
                return resp
            else:
                resp = Response(status="unauthorized")
                resp.status_code = 401
                return resp
        else:
            resp = Response(status="unauthorized")
            resp.status_code = 401

    elif request.method == "GET":
        qs = request.query_string
        if request.args.get("q") == "syndicate-to":
            syndicate_to = ["twitter.com/", "tumblr.com/", "facebook.com/"]

            r = ""
            while len(syndicate_to) > 1:
                r += "syndicate-to[]=" + syndicate_to.pop() + "&"
            r += "syndicate-to[]=" + syndicate_to.pop()
            resp = Response(
                content_type="application/x-www-form-urlencoded", response=r
            )
            return resp
        resp = Response(status="not implemented")
        resp.status_code = 501
        return resp
    return "", 501


@app.route("/list_mentions")
def print_mentions():
    r = requests.get(
        "https://webmention.io/api/mentions?target=https://kongaloosh.com/",
        headers={"Accept": "application/json"},
    ).json()["links"]
    print(r)
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
def show_drafts():
    if not session.get("logged_in"):
        abort(401)
    drafts_location = "drafts/"
    entries = [
        file_parser_json(os.path.join(drafts_location, f))
        for f in os.listdir(drafts_location)
        if f.endswith(".json")
    ]
    return render_template("drafts_list.html", entries=entries)


@app.route("/drafts/<name>", methods=["GET", "POST"])
def show_draft(name):
    if request.method == "GET":
        if not session.get("logged_in"):
            abort(401)
        draft_location = f"drafts/{name}"
        entry = get_post_for_editing(draft_location)
        return render_template("edit_entry.html", entry=entry, type="draft")

    if request.method == "POST":
        if not session.get("logged_in"):
            abort(401)
        data = post_from_request(request)

        if "Save" in request.form:  # if we're updating a draft
            file_name = f"drafts/{name}"
            entry = file_parser_json(file_name)
            update_json_entry(data, entry, g=g, draft=True)
            return redirect("/drafts")

        if "Submit" in request.form:  # if we're publishing it now
            location = add_entry(request, draft=True)
            # this won't always be the slug generated
            if os.path.isfile(f"drafts/{name}.json"):
                os.remove(f"drafts/{name}.json")
            return redirect(location)
    return "", 405  # Method Not Allowed


@app.route("/ap_subscribe", methods=["POST"])
def subscribe_request():
    print(request, request.method)
    if request.method == "POST":
        #  curl -g https://mastodon.social/.well-known/webfinger/?resource=acct:kongaloosh@mastodon.social
        social_name = request.form["handle"]
        user_name, social_domain = social_name.split("@")
        response = requests.get(
            "https://"
            + social_domain
            + "/.well-known/webfinger/?resource=acct:"
            + social_name
        )
        print(response, response.json())
        links = response.json()["links"]
        for link in links:
            if link["rel"] == "http://ostatus.org/schema/1.0/subscribe":
                print(link["template"].format(uri="@kongaloosh.com@kongaloosh.com"))
                return redirect(
                    link["template"].format(uri="@kongaloosh.com@kongaloosh.com")
                )
    return "", 501


@app.route("/ap_follow", methods=["POST"])
def follow_request():
    print(request, request.method)
    if not session.get("logged_in"):  # check permissions before deleting
        abort(401)
    if request.method == "POST":
        #  curl -g https://mastodon.social/.well-known/webfinger/?resource=acct:kongaloosh@mastodon.social
        social_name = request.form["handle"]
        user_name, social_domain = social_name.split("@")
        url = "https://" + social_domain + "/@" + user_name
        data = json.load(open("followers.json"))
        data["following"].append({"actor": social_name, "url": url})
        with open("followers.json", "w") as jsonf:
            jsonf.write(json.dumps(data))

        r = requests.post(
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


@app.route("/followers", methods=["GET"])
def follower_list():
    followers = json.load(open("followers.json"))
    print(followers)
    # followers = []
    return render_template("followers.html", followers=followers["following"])


@app.route("/following/<account>", methods=["GET"])
def follower_individual(account):
    followers = json.load(open("followers.json"))
    print(account, account in followers["following"])
    for actor in followers["following"]:
        if actor["actor"] == account:
            # account =  followers['following'][int(account)]
            return render_template("follower.html", follower=actor)

    return redirect("/404")


@app.route("/already_made", methods=["GET"])
def post_already_exists():
    return render_template("already_exists.html")


if __name__ == "__main__":
    app.run(debug=True)
