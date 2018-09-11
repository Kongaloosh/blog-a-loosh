import python
# from instagram.client import InstagramAPI
import ConfigParser

config = ConfigParser.ConfigParser()
config.read('config.ini')



access_token = config.get('Instagram', 'AccessToken')
client_secret = config.get('Instagram', 'ClientSecret')
api = InstagramAPI(access_token=access_token, client_secret=client_secret)
recent_media, next_ = api.user_recent_media(user_id="userid", count=10)


