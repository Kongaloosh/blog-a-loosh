import python
from instagram.client import InstagramAPI

access_token = "YOUR_ACCESS_TOKEN"
client_secret = "YOUR_CLIENT_SECRET"
api = InstagramAPI(access_token=access_token, client_secret=client_secret)
recent_media, next_ = api.user_recent_media(user_id="userid", count=10)


api.