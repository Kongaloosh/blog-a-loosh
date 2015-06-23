__author__ = 'alex'
import tweepy

def get_api(cfg):
    auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
    auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
    return tweepy.API(auth)

def main(tweet, photo=None):
    # Fill in the values noted in previous step here
    cfg = {
        "consumer_key": "DVjfycLdIZzr0gzC442VfEmjd",
        "consumer_secret": "PFvWgbQvvLVJb5lhJxDlWAIgXd7X5Yt7fh08nd69Hi2eRaI04q",
        "access_token": "785209428-XTDjPkQ3a48Z32rXoT6st9SAqcAj1IoVEvQJxEvM",
        "access_token_secret": "NX7iD7CEmLimGwWQjqzZ9xHwGLSasWVp8yt3dvg0DmCIg"
    }

    api = get_api(cfg)
    # tweet = "Hello, world! I'm playing with an API"
    if photo:
        print("photo")
        status = api.update_with_media(filename="tweet.jpg", file=photo, status=tweet)
    else:
        print("no photo")
        status = api.update_status(status=tweet)
    return ('http://twitter.com/{name}/status/{id}'.format(name=status.user.screen_name, id=status.id))

if __name__ == "__main__":
    main()
