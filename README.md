# IndieAnndroid


### What the heckbicuit is this?

I built this as a little hacked-together example of a flask [indieweb site](http://indiewebcamp.com/). 

In short, the indieweb is about maintating control of your data and self-publishing on your own site.

I use this to power [kongaloosh.com](http://kongaloosh.com), my blog. I post my photos, updates, and anything else here and it gets whisked down the internet tubes to all the other social-media sites I use afterwards. This is my hub on the internet.

### What state is this project in?

Spaghetti. 

Right now, to varying degrees of effectiveness, it can:
  
  * what-you-see-is-what-you-get posting interface [NEW AND IMPROVED!]
  * recieve entries via a micropub endpoint using indieauth
  * syndicate out to twitter and facebook using [bridgy](https://brid.gy/)
  * bulk upload images (including mobile upload)
  * post images
  * post albums full of images
  * recieve webmentions using [webmention.io](https://webmention.io/)
  * send webmentions
  * delete posts
  * save and create drafts
  * Indie-actions allowing people to auto-like, & auto-reply on instagram and twitter
  * auto-add locations to posts, including placenames and geonames ids
  * recieve linked data notifications
  * Linking hashtags back to a stream using that tag



In short, it has most of the functionality of an indieweb site. 

Keep in mind, I'm not a web-developer. That, and I just wanted to build this as rapidly as possible. 

There's still a large degree of testing which is yet to be done. Proceed with caution. 

### How do I use this?

You'll need your own server and domain name. You can register domain names with sites like [name cheap](https://www.namecheap.com/) and you can get cheap server space with [digital ocean](https://www.digitalocean.com/). [This is a really helpful tutorial on deploying flask apps on digital ocean](http://blog.marksteve.com/deploy-a-flask-application-inside-a-digitalocean-droplet).

Right now, the details in the template are my own. They details link to my site and my social accounts. This You'll need to change these.

Also, you'll find a folder of config files. Among them are the password and username for the site's login. **change these to something private**. From there, if you want to syndicate to other sites, you'll need twitter API keys. Find these, add these, and keep them *secret*.

From there, sign up for [indieauth](https://indieauth.com/). This allows you to authenicate on other sites using your own domain. These include sites like [Own Your Gram](https://ownyourgram.com/), which automatically posts your instagram photos back to your own site; and [Quill](http://quill.p3k.io/), an editor which will post notes to your site.

### Where is the data stored?

The data is kept in a human-readable format as .md files, and a more machine-readable format as .json in a folder called data. All other multimedia is kept alongside their respective .md and .json files. The data folder is broken down by year/month/day. Additionally we keep a sqlite database which maintains a record of posts, their location, and what tags are associated with them. However, this can all be inferred by looking at the .md files.

### Roadmap

1. (maybe) write a script which auto-magically configures social-keys
2. testing
3. Search-bar
4. Better and more complete integration of Linked-Data Notifications and Activity Streams
5. Better integration of twitter (auto-lookup for handles, etc)
