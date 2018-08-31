__author__ = 'kongaloosh'

from markdown import Extension
from markdown.preprocessors import Preprocessor
import re
from PIL import Image
from datetime import datetime
import os

old_prefix = '/home/deploy/kongaloosh/'
new_prefix = '/mnt/volume-nyc1-01/'

# the regular expression to find albums
ALBUM_GROUP_RE = re.compile(
    r'''(@{3,})(?P<album>((.)|(\n))*?)(@{3,})'''
)

def move(loc, date):
    """"
    Moves an image, scales it and stores a low-res with the blog post and a high-res in a long-term storage folder.
    :param loc: the location of an image
    :param loc: the date folder to which an image should be moved
    """
    if date is None:
        date = datetime.now()

    date_suffix = "data/{0}/{1}/{2}/".format(
        date.year,
        date.month,
        date.day
    )

    file_name = loc[13:]                                                    # remove the '/images/temp/'
    target_file_path = new_prefix + loc[1:]
    if not os.path.exists(new_prefix+'images/' + date_suffix):              # if the target directory doesn't exist ...
        print new_prefix
        os.makedirs(os.path.dirname(new_prefix+'images/'+date_suffix))      # ... make it.
    img = Image.open(target_file_path)                                      # open the image from the temp
    img.save(new_prefix+'images/'+date_suffix+file_name.lower())            # open the new location

    max_height = 500                                            # maximum height
    img = Image.open(target_file_path)                          # open the image in PIL
    h_percent = (max_height / float(img.size[1]))               # calculate what percentage the new height is of the old
    w_size = int((float(img.size[0]) * float(h_percent)))       # calculate the new size of the width
    img = img.resize((w_size, max_height), Image.ANTIALIAS)     # translate the image
    try:
        if not os.path.exists(old_prefix+date_suffix):              # if the blog's directory doesn't exist
            os.makedirs(os.path.dirname(old_prefix+date_suffix))    # make it
        img.save(old_prefix+date_suffix+file_name.lower())          # image save old_prefix
    except OSError:
        pass
    # Result:
    # Scaled optimised thumbnail in the blog-source next to the post's json and md files
    # Original-size photos in the self-hosting image server directory
    os.remove(target_file_path)
    return "/" + date_suffix+file_name.lower()                          # of form data/yyyy/mm/dd/name.extension


def run(lines, date=None):
    """
    Finds all references to images, removes them from their temporary directory, moves them to their new location, 
    and replaces references to them in the original post text.
    :param lines: the text of an entry which may, or may or may not have photos.
    :param date: the date this post was made.
    """

    # 1. find all the references to images
    text = lines
    last_index = -1
    finished = False
    while not finished:
        # given the substitution, the new entries will likely be longer
        # ie. images/temp/name.jpg is shorter than data/yyyy/mm/dd/name
        # substituting immediately in will cause overlap
        # we need this loop to go over iteratively; we keep track of where we were last with
        collections = ALBUM_GROUP_RE.finditer(text)
        if collections:                                             # if there's an image match
            current_index = 0
            while True:
                try:
                    collection = collections.next()
                    current_index += 1
                    if current_index > last_index:
                        # split a daisy chain of images in an album
                        images = re.split(  # split the collection into images
                            "(?<=\){1})[ ,\n,\r]*-*[ ,\n,\r]*(?=\[{1})",
                            collection.group('album')
                        )
                        album = ""                                      # where we place reformatted images
                        for index in range(len(images)):                # for image in the whole collection
                            last_index = current_index                  # update

                            image_ref = re.search(
                                "(?<=\({1})(.)*(?=\){1})",
                                images[index]) \
                                .group()                                # get the image location

                            alt = re.search(
                                "(?<=\[{1})(.)*(?=\]{1})",
                                images[index]
                            ).group()                                   # get the text

                            if image_ref.startswith("/images/temp/"):   # if the location is in our temp folder...
                                image_ref = move(image_ref, date)       # ... move and resize photos
                            album += "[%s](%s)" % (alt, image_ref)      # album
                            if index != len(images) - 1:                # if this isn't the last image in the set...
                                album += "-\n"                          # ... then make room for another image

                        current_index = last_index

                        if album is not "":                             # if the album isn't empty
                            text = '%s@@@%s@@@%s' % (text[:collection.start()],  # sub it into where the old images were
                                                   album,
                                                   text[collection.end():])
                        last_index = current_index
                        break
                except StopIteration:
                    if current_index == last_index or last_index == -1:
                        finished = True
                    break
        else:
            finished = True
            break
    return text

if __name__ == "__main__":
    lines = u'@@@\r\n[](/data/2017/7/4/img_6817.jpg)-\r\n[](/data/2017/7/4/img_0281.jpg)-\r\n[](/data/2017/7/4/img_6786.jpg)\r\n@@@'

    lines_3 = """
        I flew down to Wyoming on the weekend to go see the Solar Eclipse. This was a spur of the moment trip; a family friend is an amateur astronomer and was planning on driving down on the weekend to be able to catch the eclipse. One problem with their plan: motel rooms within driving distance of the totality were going for $1200 or more on the evening before the eclipse. One solution: motel rooms within flying distance of the totality were going for 90$ a night the evening before the eclipse. 

        @@@[](/data/2017/8/25/img_6838.jpg)-[](/data/2017/8/25/img_6834.jpg)-[](/data/2017/8/25/img_6837.jpg)@@@

        Instead of driving down, we all flew down from Calgary, stayed the night in Montana, and on the morning of the eclipse flew in to [Riverton, Wyoming](https://en.wikipedia.org/wiki/Riverton,_Wyoming), a town of roughly 11,000 people. 

Why the fuss of trying to get onto the totality line? In many places you could see the sun turn into a sliver during the eclipse, but only if you had the protective eyewear. In a few places stretching across the east to west of the U.S. you were able to see the eclipse in it's totality; for just over two minutes the sun would be entirely blocked by the moon, allowing you to see the sun's corona.

### A Surreal Setting

They really pulled out all the stops in Riverton for the eclipse. There were a couple of people with walkie-talkies and an ATV set up as temporary ground-control. On arrival they pointed you towards a breakfast barbecue they'd setup for all the planes which flew in for the day. 

Apparently we weren't the only people to come up with this plan.



@@@[](/data/2017/8/25/img_7309.jpg)-[](/data/2017/8/25/img_7302.jpg)@@@



One of the most interesting aspects was the sheer number of planes. There were a score of private jets on the ramp, including a challenger, and probably close to a hundred small personal planes on the tarmac and grass surrounding the airstrip. A few people were camping next to their planes overnight. A number of the private jets erected shelters and had party games under their wings. 

It was like a tailgate party for plane people. 

11,000 people live in this town and it suddenly had hundreds of millions of dollars in planes sitting on the tarmac, only to leave when the eclipse was over.

### The Most Impressive Sight I've Seen

To view the eclipse we brought a number of welders glasses which we could layer depending on the cloud-cover and intensity of the sunlight. At first you could only see a little dimple in the top of the sun. As the dimple grew and the moon covered more of the sun, it got dimmer and dimmer, but not fast enough that you noticed it immediately. Even when mostly covered, the sun never really seemed like it was covered. 



@@@
[](/data/2017/8/25/img_6859.jpg)
@@@
    """

    lines_2 = """
This year I went to DLSS and RLSS in Toronto. The introductory talks were probably the best intro to neural nets talks I'd seen: the talks were tight and intuitive without having to water down the technical details. 


@@@
[](/data/2018/8/1/8b4d24be-139a-4a28-ace3-7f9b78123729.jpeg)-
[](/data/2018/8/1/71f72258-1977-4253-8578-dd338f9f9f7f.jpeg)
@@@


The number of people cramming in for the summer school was surprising. It's really great to see how interest in Reinforcement Learning has picked up in recent years.


@@@
[](/data/2018/8/1/373ffed9-98f4-4f4d-8c40-54eca75fbe83.jpeg)
@@@


Being back in Toronto for the summer means that I had I had the chance to wander around kensington market again. This time, sans persistent summer flu. With a few fellow students in tow, Anna and I hit up [Yarns Untangled](http://yarnsuntangled.com/), the first LYS I ever visited. We picked up needles and yarn to teach some people how to knit while sharing a pitcher of beer on the patio across the street. 

Against my better judgement, I picked up a few indie-dyed skeins of yarn. One from [lichen and lace](https://lichenandlace.com/)---a dyer on the east coast---and one from [fiesty fibers](https://www.instagram.com/feistyfibres)---a local Torontonian who happened to be having a trunk sale while we were in town.

Who knows what the skeins will end up being. I suppose I can always teach myself how to knit socks.


@@@
[](/data/2018/8/1/55397df7-bf7f-47b1-aac1-e04c53d043ef.jpeg)-
[](/data/2018/8/1/img_2326.jpg)
@@@


Having the chance to hit up local yarn stores with active communities reminds me of what I'm missing out on in Edmonton. YU felt like a community hub. People would would  gather on their couches, chatting with each other while they worked on whatever project they were carrying with them. 

While I was waiting for a few people I sat myself down next two a couple of women and felt right at home chatting with them about how they originally started knitting and what they were currently working on. It's really refreshing to have these spaces which people can come into and join without any introduction: it's really healthy to have these communities where people can just feel at home.


@@@
[](/data/2018/8/1/59fcad57-4bae-4e51-837a-9c7914c5e6a0.jpeg)-
[](/data/2018/8/1/71bdf3e8-6738-4baf-acc9-15d57be47366.jpeg)-
[](/data/2018/8/1/16df597c-2df1-49f6-b846-9c2fa7dc745d.jpeg)
@@@


I have no regrets about wandering into [Little Pebbles](http://little-pebbles.com/) to have Japanese dessert _before_ meeting with some of the other students for brunch. I had this little matcha tiramisu which was carefully constructed in this little box which reminded me of sake drinking vessels. Interestingly, instead of a brandy base, at the bottom of the tiramisu was a bit of red bean paste to sweeten and balance out the earthy matcha flavours.

The whole place was bright and funky without being overwhelmingly ornate. It was an unusual and pleasant surprise to see the little signs up on the tables which politely notified people that they had to put their electronics away during peak hours--an attempt to foster community and conversation.


@@@
[](/data/2018/8/1/8c1074f6-311e-414a-aa7b-deea9673f242.jpeg)-
[](/data/2018/8/1/b9e2e7cf-0ef4-49e0-a2af-642d4001f865.jpeg)
@@@


When wandering around the city I found a whole bunch of cute ceramics, which make me regret not having kept up with pottery after highschool. Maybe I'll need to eventually fix that and take a course at Edmonton's  city arts centre.


@@@
[](/data/2018/8/1/69394683-9d8d-4611-9dec-0c342f1cd66b.jpeg)-
[](/data/2018/8/1/af489a04-505b-44f9-831d-72c95efe8b00.jpeg)
@@@


The closest coffee shop to where I was staying was [Hopper](https://www.instagram.com/hopper_coffee_toronto). It was a cute little place with great snacks and even better espresso. In spite of being fairly spartan in terms of quantity of furniture, what they had was really funky---i.e., campbell's soup can tables. 


@@@
[](/data/2018/8/1/9b0b8b39-6c6e-4b3e-9f1e-30c96a4db4b1.jpeg)-
[](/data/2018/8/1/afad5904-695c-4693-9d23-4c3d802b56a5.jpeg)
@@@


I finally managed to try [goldstruck](http://www.goldstruck.ca/)--a place I wanted to visit while I was interning in Toronto, but never quite had the chance to. They definitely themed the place appropriately. Walking down the stairs into the sub-terrainian coffeeshop, you're greeted by the warm glow of industrial lighting and mining-inspired decor. Even the bathroom has these massive wooden barn-doors which slide open.


@@@
[](/data/2018/8/1/2ab058cc-44a7-433c-a0d1-f0fbef36f2e5.jpeg)-
[](/data/2018/8/1/5b727404-10fe-4c98-938b-7dd08eff4bd0.jpeg)-
[](/data/2018/8/1/cfecd0dd-474c-40a6-a370-966ba79c647a.jpeg)
@@@


Of course, my favourite little cafe was _sorry_: a little gem that's tucked away in a corner, unapologetically making great espresso and pastries.
"""

    print run(lines, date=None)
    print run(lines_2, date=None)
