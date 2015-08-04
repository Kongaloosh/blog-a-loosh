# IndieAnndroid


### What the heck is this?

I built this as a little hacked-together example of a flask [indieweb site](http://indiewebcamp.com/). In short, the indieweb is about maintating control of your data and self-publishing on your own site. 

### What state is this project in?

Spaghetti. 

Right now, to varying degrees of effectiveness, it can:
  
  * recieve entries via a micropub endpoint using indieauth
  * syndicate out to twitter
  * post images
  * recieve webmentions using webmention.io
  * send webmentions

There's still a large degree of testing which is yet to be done. Proceed with caution. 

### How do I use this?

You'll need your own server and domain name. You can register domain names with sites like [name cheap](https://www.namecheap.com/) and you can get cheap server space with [digital ocean](https://www.digitalocean.com/). [This is a really helpful tutorial on deploying flask apps on digital ocean](http://blog.marksteve.com/deploy-a-flask-application-inside-a-digitalocean-droplet).

Right now, the details in the template are my own. They details link to my site and my social accounts. This You'll need to change these.

Also, you'll find a folder of config files. Among them are the password and username for the site's login. **change these to something private**. From there, if you want to syndicate to other sites, you'll need twitter API keys. Find these, add these, and keep them *secret*.

From there, sign up for [indieauth](https://indieauth.com/). This allows you to authenicate on other sites using your own domain. These include sites like [Own Your Gram](https://ownyourgram.com/), which automatically posts your instagram photos back to your own site; and [Quill](http://quill.p3k.io/), an editor which will post notes to your site.

### Where is the data stored?

The data is kept as .md files in a folder called data. All other multimedia is kept alongside their respective textual .md files. The data folder is broken down by year/month/day. Additionally we keep a sqlite database which acts as a cache, maintaining the most recent posts, their location, and what tags are associated with them.

### Roadmap

1. clean-up the social-media refrences so other people can simply drop their own details in
2. (maybe) write a script which auto-magically does this
3. testing
4. fetching of reply-to details for presentation
5. better formatting of reply-to and mentions
6. better formatting fo entries

