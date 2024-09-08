#!/usr/bin/python
# coding: utf-8
import configparser
import json
import markdown
import os
import re
import requests
import sqlite3
from PIL import Image, ExifTags
from contextlib import closing
from datetime import datetime
from dateutil.parser import parse
from flask import (
    Flask,
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
)
from jinja2 import Environment
from pysrc.markdown_hashtags.markdown_hashtag_extension import HashtagExtension
from pysrc.markdown_albums.markdown_album_extension import AlbumExtension
from pysrc.python_webmention.mentioner import get_mentions
import slugify
from pysrc.authentication.indieauth import checkAccessToken
from pysrc.file_management.file_parser import (
    create_json_entry,
    update_json_entry,
    file_parser_json,
)
from pysrc.file_management.markdown_album_pre_process import run
from pysrc.file_management.markdown_album_pre_process import new_prefix

jinja_env = Environment(extensions=["jinja2.ext.with_"])

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
PHOTOS_URL = config.get("PhotoLocations", "URLPhotos")

print(DATABASE, USERNAME, PASSWORD, DOMAIN_NAME)

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config["STATIC_FOLDER"] = os.getcwd()
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


def get_entries_by_date():
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


def get_most_popular_tags():
    """gets the tags (excluding post type declarations) and returns them in descending order of usage.

    Returns:
        List of tags in descending order by usage.
    """
    cur = g.db.execute(
        """
        SELECT category
        FROM (
            SELECT category as category, count(category) as count
            FROM categories
            GROUP BY category
        )ORDER BY count DESC
    """
    )
    tags = [row for (row,) in cur.fetchall()]
    # strip type declarations
    for element in ["None", "image", "album", "bookmark", "note"]:
        try:
            tags.remove(element)
        except ValueError:
            pass
    return tags


def resolve_placename(location: str) -> tuple[str, int] | tuple[None, None]:
    """Given a location, returns the closest placename and geoid of a location.
    Args:
        location (str): the geocoords of some location
    Returns:
        placename (str), geoid (int): the name resolution and geoid of the place resolved
    """
    try:
        # we take off the first four characters 'geo:'
        # and then we split
        (lat, long) = location[4:].split(",")

        # no clue what's going on here :o
        try:
            float(long)
        except ValueError:
            long = re.search("(.)*(?=;)", long).group(0)

        #  make a request to the geonames API to find nearest placename
        geo_results = requests.get(
            "http://api.geonames.org/findNearbyPlaceNameJSON?style=Full&radius=5&lat="
            + lat
            + "&lng="
            + long
            + "&username="
            + GEONAMES
        )

        place_name = geo_results.json()["geonames"][0]["name"]
        if geo_results.json()["geonames"][0]["adminName2"]:
            place_name += ", " + geo_results.json()["geonames"][0]["adminName2"]
        elif geo_results.json()["geonames"][0]["adminName1"]:
            place_name += ", " + geo_results.json()["geonames"][0]["adminName1"]
        else:
            place_name += ", " + geo_results.json()["geonames"][0]["countryName"]
        return place_name, geo_results.json()["geonames"][0]["geonameId"]
    except IndexError:
        return None, None


def post_from_request(request=None):

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
    if request:
        try:
            # if the photo is a file, then go to beginning; otherwise, null.
            files = request.files.getlist("photo_file[]")
            if type(files) is type(list()):
                if len(files) == 0:
                    data["photo"] = None
                else:
                    data["photo"] = request.files.getlist("photo_file[]")
            else:
                data["photo"].seek(0, 2)
                if data["photo"].tell() < 1:
                    data["photo"] = None
                else:
                    data["photo"] = [request.files["photo_file"]]
        except KeyError:
            pass

        try:
            data["old_photos"] = request.form["photo"]
        except KeyError:
            pass
        try:
            trips = []
            geo = request.form.getlist("geo[]")
            location = request.form.getlist("location[]")
            date = request.form.getlist("date[]")
            # if the trips are well-formatted, then parse them accordingly
            if len(geo) == len(location) and len(location) == len(date):
                while True:
                    try:
                        trips.append(
                            {
                                "location": geo.pop(0),
                                "location_name": location.pop(0),
                                "date": date.pop(0),
                            }
                        )
                    except IndexError:
                        break
            data["travel"] = {}
            data["travel"]["trips"] = trips
            if len(trips) > 0:  # if there's more than one location, make the map
                markers = "|".join(
                    [destination["location"][4:] for destination in trips]
                )  # make the trips
                r = requests.get(
                    "https://maps.googleapis.com/maps/api/staticmap?&maptype=roadmap&size=500x500&markers=color:green|{0}&path=color:green|weight:5|{1}&key={2}".format(
                        markers, markers, GOOGLE_MAPS_KEY
                    )
                )
                data["travel"]["map"] = r.content
        except KeyError:
            pass

        try:
            # create an event
            data["event"] = {}
            for key in ["dt_start", "dt_end", "event_name"]:
                if request.form[key] == "":
                    data["event"] = None
                    break
                else:
                    data["event"][key] = request.form[key]
        except KeyError:
            pass

        for title in request.form:
            try:
                # check if the element is already written
                # we privilege files over location refs
                if data[title] is None:
                    data[title] = request.form[title]
            except KeyError:
                data[title] = request.form[title]

        for key in data:
            if data[key] == "None" or data[key] == "":
                data[key] = None

        if data["published"]:
            data["published"] = parse(data["published"])
    return data


def get_post_for_editing(draft_location, md=False):

    entry = file_parser_json(draft_location, md=False)
    if entry["category"]:
        entry["category"] = ", ".join(entry["category"])

    if entry["in_reply_to"]:
        entry["in_reply_to"] = ", ".join([e["url"] for e in entry["in_reply_to"]])

    if entry["published"]:
        try:
            entry["published"] = entry["published"].strftime("%Y-%m-%d")
        except AttributeError:
            entry["published"] = None
    return entry


def syndicate_from_form(creation_request, data):
    """Using the data from a post just submitted, syndicate to social networks.
    Args:
        creation_request (Response): the response from an /add post form.
        data (dict): represents a new entry.
    """
    post_loc = "http://" + DOMAIN_NAME + data["url"]
    # Check to see if the post is in reply to another post and send a mention
    try:
        for reply in data["in_reply_to"]:
            app.logger.info("MENTIONING: {0} \nTO\n {1}".format(post_loc, reply))
            requests.post(
                "https://fed.brid.gy/webmention",
                data={
                    "source": "https://" + DOMAIN_NAME + data["url"],
                    "target": reply,
                },
            )
            # send_mention(post_loc, reply)
    except TypeError:
        pass

    if creation_request.form.get("twitter"):
        # if we're syndicating to twitter, spin off a thread and send the request.
        send_tweet(data)
    if creation_request.form.get("bridgy_twitter"):
        t = Timer(30, bridgy_twitter, [data["url"]])
        t.start()


def update_entry(update_request, year, month, day, name, draft=False):
    data = post_from_request(update_request)
    if data["location"] is not None and data["location"].startswith("geo:"):
        # get the place name for the item in the data.
        (place_name, geo_id) = resolve_placename(data["location"])
        data["location_name"] = place_name
        data["location_id"] = geo_id

    location = "{year}/{month}/{day}/{name}".format(
        year=year, month=month, day=day, name=name
    )
    data["content"] = run(data["content"], date=data["published"])

    file_name = "data/{year}/{month}/{day}/{name}".format(
        year=year, month=month, day=day, name=name
    )
    # get the file which will be updated
    entry = file_parser_json(file_name + ".json", g=g)
    update_json_entry(data, entry, g=g, draft=draft)
    syndicate_from_form(update_request, data)
    return location


def add_entry(creation_request, draft=False):
    """Adds a post based on a request.
    Args:
        creation_request (request): the request received from a post at /add or /edit
        draft (bool): A flag determining whether the post should be considered a draft. If true, saves instead of post.
    Returns:
        location (str): the url of the new post.
    """
    data = post_from_request(creation_request)
    if data["published"] is None:  # we're publishing it now; give it the present time
        data["published"] = datetime.now()
    # find all images in albums and move them
    data["content"] = run(data["content"], date=data["published"])

    # if we were given a geotag
    if data["location"] is not None and data["location"].startswith("geo:"):
        (place_name, geo_id) = resolve_placename(data["location"])  # get the placename
        data["location_name"] = place_name
        data["location_id"] = geo_id
        # todo: you'll be left with a rogue 'location' in the dict... should clean that...

    location = create_json_entry(data, g=g)  # create the entry
    syndicate_from_form(creation_request, data)
    requests.post(
        "https://fed.brid.gy/webmention",
        data={
            "source": "https://" + DOMAIN_NAME + data["url"],
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
        print("\n\n\n\n ---- Looking at AS ---- \n\n\n")
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

    try:
        entries = entries[:10]  # get the 10 newest
    except IndexError:
        entries = None  # there are no entries

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
            try:
                geo_coords.append(entry["location"][4:].split(";")[0])
            except (AttributeError, TypeError):
                pass
            try:
                trips = entry["travel"]["trips"]
                if len(trips) > 0:  # if there's more than one location, make the map
                    geo_coords += [destination["location"][4:] for destination in trips]
            except (KeyError, TypeError):
                pass

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
def page_not_found(e):
    return render_template("server_error.html"), 500


@app.route("/add", methods=["GET", "POST"])
def add():
    """The form for user-submission"""
    if request.method == "GET":
        tags = get_most_popular_tags()[:10]
        return render_template(
            "edit_entry.html", entry=post_from_request(), popular_tags=tags, type="add"
        )

    elif request.method == "POST":  # if we're adding a new post
        if not session.get("logged_in"):
            abort(401)

        if "Submit" in request.form:
            # thread = threading.Thread(target=add_entry, args=(
            #     request))  # we spin off a thread to create
            # album processing can take time: we want to spin it off to avoid worker timeouts.
            # thread.start()
            return redirect(add_entry(request))

        elif "Save" in request.form:  # if we're simply saving the post as a draft
            data = post_from_request(request)
            return redirect(create_json_entry(data, g=g, draft=True))

        # else:
        #     return redirect("/")

        # else:
        #     flash("Invalid")
        #     return redirect('/add')


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
        tags = get_most_popular_tags()[:10]
        return render_template("photo_stream.html")

    elif request.method == "POST":  # if we're adding a new post
        if not session.get("logged_in"):
            abort(401)


@app.route("/delete_entry/e/<year>/<month>/<day>/<name>", methods=["POST", "GET"])
def delete_entry(year, month, day, name):
    if not session.get("logged_in"):
        abort(401)
    else:

        totalpath = "data/{0}/{1}/{2}/{3}".format(year, month, day, name)
        if not os.path.isfile(totalpath + ".json"):
            return redirect("/")
        entry = file_parser_json(totalpath + ".json")

        if type(entry["photo"]) == type(list()):
            for photo in entry["photo"]:
                os.remove(photo)

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
            app.logger.info("file " + uploaded_file.filename)
            file_loc = file_path + "{0}".format(uploaded_file.filename)
            image = Image.open(uploaded_file)
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == "Orientation":
                    break
            exif = dict(image._getexif().items())

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
                    request.data,
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
            "http://api.geonames.org/wikipediaSearchJSON?username=kongaloosh&q=" + query
        )
        return jsonify(resp.json()), resp.status_code, resp.headers.items()
    else:
        return redirect("/404"), 404


@app.route("/recent_uploads", methods=["GET", "POST"])
def recent_uploads():
    """
    :returns a formatted list of all the images in the current day's directory
    """
    if request.method == "GET":

        directory = ORIGINAL_PHOTOS_DIR

        try:
            if request.args.get("stream"):
                insert_pattern = "%s"
            else:
                insert_pattern = "[](%s)"
        except KeyError:
            insert_pattern = "[](%s)"

        file_list = []
        for file in os.listdir(directory):
            path = PHOTOS_URL + file
            file_list.append(path)

        preview = ""
        j = 0
        while True:
            row = ""
            for i in range(0, 3):  # for every row we want to make
                image_index = (3 * j) + i
                if image_index >= len(file_list):
                    preview += """
                        <div class="row">
                            %s
                        </div>
                        """ % (
                        row
                    )
                    return preview

                image_location = file_list[image_index]
                text_box_insert = insert_pattern % image_location
                img_id = (3 * j) + i
                row += """
                        <a class="p-2 text-center" onclick="insertAtCaret('text_input','%s', 'img_%s');return false;">
                            <img src="%s" id="img_%s" class="img-fluid" style="max-height:auto; width:25%%;">
                        </a>
                    """ % (
                    text_box_insert,
                    img_id,
                    image_location,
                    img_id,
                )

            preview += """
                <div class="d-flexbox flexbox-row">
                    %s
                </div>
                """ % (
                row
            )
            j += 1

        return preview

    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)
        try:
            to_delete = json.loads(request.get_data())["to_delete"]

            if os.path.isfile(new_prefix + to_delete[len("/images/") :]):
                os.remove(new_prefix + to_delete[len("/images/") :])
                return "deleted"
        except KeyError:
            return abort(404)
    else:
        return redirect("/404"), 404


@app.route("/edit/e/<year>/<month>/<day>/<name>", methods=["GET", "POST"])
def edit(year, month, day, name):
    """The form for user-submission"""
    if request.method == "GET":
        file_name = "data/{year}/{month}/{day}/{name}.json".format(
            year=year, month=month, day=day, name=name
        )
        entry = get_post_for_editing(file_name)
        return render_template("edit_entry.html", type="edit", entry=entry)

    elif request.method == "POST":
        if not session.get("logged_in"):
            abort(401)

        if "Submit" in request.form:
            update_entry(request, year, month, day, name)

        return redirect("/")


@app.route("/e/<year>/<month>/<day>/<name>")
def profile(year, month, day, name):
    """Get a specific article"""

    file_name = "data/{year}/{month}/{day}/{name}".format(
        year=year, month=month, day=day, name=name
    )
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
                    app.logger.info(request.form.get("category[]"))
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
                if data["in_reply_to"]:
                    pass
                    # send_mention('https://' + DOMAIN_NAME +
                    #             '/e/' + location, data['in_reply_to'])

                # regardless of whether or not syndication is called for, if there's a photo, send it to FB and twitter
                try:
                    if request.form.get("twitter") or data["photo"]:
                        t = Timer(30, bridgy_twitter, [location])
                        t.start()
                except KeyError:
                    pass

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


@app.route("/list_mentions")
def print_mentions():
    print("We are here!!!!")
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
        entries = [
            f
            for f in os.listdir(inbox_location)
            if os.path.isfile(os.path.join(inbox_location, f)) and f.endswith(".json")
        ]

        for_approval = [entry for entry in entries if entry.startswith("approval_")]
        entries = [entry for entry in entries if not entry.startswith("approval_")]
        if "text/html" in request.headers.get("Accept"):
            return render_template(
                "inbox.html", entries=entries, for_approval=for_approval
            )
        elif "application/ld+json" in request.headers.get("Accept"):
            inbox_items = {}
            inbox_items["@context"] = "https://www.w3.org/ns/ldp"
            inbox_items["@id"] = "http://" + DOMAIN_NAME + "/inbox"
            inbox_items["http://www.w3.org/ns/ldp#contains"] = [
                {"@id": "http://" + DOMAIN_NAME + "/inbox/" + entry}
                for entry in entries
            ]
            resp = Response(inbox_items, content_type="application/ld+json", status=200)
            resp.data = json.dumps(inbox_items)
            return resp
        # else:
        #     resp = Response(content_type="application/ld+json", status=200)
        #     resp.data = """
        #         <inbox>
        #         a ldp:Container
        #         ldp:contains {0}
        #         </inbox>
        #         """.format([{"@id": "http://" + DOMAIN_NAME + "/inbox/" + entry} for entry in entries])
        #     return resp
        else:
            resp = Response(status=501)
            return resp
    elif request.method == "POST":
        data = json.loads(request.data)
        try:
            sender = data["actor"]["@id"]
        except TypeError:
            sender = data["actor"]
        except KeyError:
            try:
                sender = data["actor"]["id"]
            except KeyError:
                sender = None

        if (
            sender == "https://rhiaro.co.uk" or sender == "https://rhiaro.co.uk/#me"
        ):  # check if the sender is whitelisted
            # todo: make better names for notifications
            location = "inbox/" + slugify(str(datetime.now())) + ".json"
            notification = open(location, "w+")
            notification.write(request.data)
            resp = Response(status=201, headers={"Location": location})
            return resp
        else:  # if the sender isn't whitelisted
            try:
                try:
                    data["context"]
                    notification = open(
                        "inbox/approval_" + slugify(str(datetime.now())) + ".json", "w+"
                    )
                    notification.write(request.data)
                    resp = Response(status="queued")
                    resp.data = {"@id": "", "http://www.w3.org/ns/ldp#contains": []}
                    resp.status_code = 202
                    return resp
                except KeyError:
                    resp = Response(403)
                    resp.status_code = 403
                    return resp
            except requests.ConnectionError:
                resp = Response(status="unauthorized")
                resp.status_code = 403
                return resp
    else:
        resp = Response(status="Not Implemented")
        resp.status_code = 501
        app.logger.info(resp)
        return resp


@app.route("/inbox/send/", methods=["GET", "POST"])
def notifier():
    return 501


@app.route("/inbox/<name>", methods=["GET"])
def show_inbox_item(name):
    if request.method == "GET":
        entry = json.loads(open("inbox/" + name).read())
        app.logger.info((request, request.data))
        try:
            # if someone else is consuming
            if request.headers.get("Accept") == "application/ld+json":
                inbox_items = {}
                resp = Response(content_type="application/ld+json", status=200)
                resp.data = json.dumps(entry)
                return resp

            if "text/html" in request.headers.get("Accept"):
                try:
                    sender = entry["actor"]["@id"]
                except KeyError:
                    try:
                        sender = entry["actor"]["id"]
                    except KeyError:
                        sender = entry["@id"]
                except TypeError:
                    sender = entry["actor"]
                return render_template(
                    "inbox_notification.html", entry=entry, sender=sender
                )

            else:
                # app.logger.info(request.headers.get('Accept'))
                # resp = Response(content_type="application/ld+json", status=200)
                # resp.data = """
                #     <inbox>
                #     a ldp:Container
                #     ldp:contains {0}
                #     </inbox>
                #     """.format(str(entry))
                inbox_items = {}
                resp = Response(content_type="application/ld+json", status=200)
                resp.data = json.dumps(entry)
            return resp

        except TypeError:
            # app.logger.info("empyt")
            # resp = Response(content_type="application/ld+json", status=200)
            # resp.data = """
            #     <inbox>
            #     a ldp:Container
            #     ldp:contains {0}
            #     </inbox>
            #     """.format(str(entry))
            # return resp
            inbox_items = {}
            resp = Response(content_type="application/ld+json", status=200)
            resp.data = json.dumps(entry)
            return resp


@app.route("/drafts", methods=["GET"])
def show_drafts():
    if request.method == "GET":
        if not session.get("logged_in"):
            abort(401)
        drafts_location = "drafts/"
        entries = [
            drafts_location + f
            for f in os.listdir(drafts_location)
            if os.path.isfile(os.path.join(drafts_location, f)) and f.endswith(".json")
        ]
        entries = [file_parser_json(entry) for entry in entries]
        return render_template("drafts_list.html", entries=entries)


@app.route("/drafts/<name>", methods=["GET", "POST"])
def show_draft(name):
    if request.method == "GET":
        if not session.get("logged_in"):
            abort(401)
        draft_location = "drafts/" + name + ".json"
        entry = get_post_for_editing(draft_location)
        return render_template("edit_entry.html", entry=entry, type="draft")

    if request.method == "POST":
        if not session.get("logged_in"):
            abort(401)
        data = post_from_request(request)

        if "Save" in request.form:  # if we're updating a draft
            file_name = "drafts/{0}".format(name)
            entry = file_parser_json(file_name + ".json")
            update_json_entry(data, entry, g=g, draft=True)
            return redirect("/drafts")

        if "Submit" in request.form:  # if we're publishing it now
            location = add_entry(request, draft=True)
            # this won't always be the slug generated
            if os.path.isfile("drafts/" + name + ".json"):
                os.remove("drafts/" + name + ".json")
            return redirect(location)


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

    # response = requests.get("https://"+social_domain+"/.well-known/webfinger/?resource=acct:"+social_name)
    # print(response, response.json())
    # links = response.json()['links']
    # for link in links:
    #     if link['rel'] == 'http://ostatus.org/schema/1.0/subscribe':
    #         print(link['template'].format(uri='@kongaloosh.com@kongaloosh.com'))
    #         return redirect(link['template'].format(uri="@kongaloosh.com@kongaloosh.com"))


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
