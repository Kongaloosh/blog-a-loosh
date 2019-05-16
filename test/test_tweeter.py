import unittest
from pysrc.posse_scripts.tweeter import *


class MyTestCase(unittest.TestCase):
    def test_image_ref_finder(self):
        image_refs = find_all_images("""
            I'm going back through my dive logbook after a three year diving hiatus. @@@@[](wow)-\n[img_loc_2](wow2)@@@ The software I use to track my dives has become an ungodly mess of company acquisitions and software maintenance. Turns out the company that made my dive-computer was bought out by scuba-pro. To even get my hands on the software to open my dive-log file, I had to scour looking for a hidden link that would take me to the SmartTrak site. That wasn't even enough alone, I had to engage in browser witchcraft to coerce the site to not redirect me to scuba-pro's main site. The file is _nowhere else_, at least by my searching. @@@@[img_loc](wow3)@@@ Interesting that no one liked it enough to keep a mirror of it... Of course, the software didn't solve my problems. _oh no_. The dates were incorrect on some of my dives. Another example malady of poor software support: I could turn the background of dive profiles _gradient olive green_, but I could not edit basic dive info---e.g., the date and location of a dive. For the first-time in my life, I'm actually facing a deprecation of software that I _need_. It's important that I keep the data I collect when I'm diving. After going through old dev-forums and [dive-forums](https://www.scubaboard.com/community/threads/smart-trak-to-logtrak-import.546613/page-2), I found [a converter](https://thetheoreticaldiver.org/rch-cgi-bin/smtk2ssrf.pl) which takes shameful SmartTrack files and converts them into a modified XML for use with [SubSurface](https://subsurface-divelog.org/download/). At least I can coerce the file into being read as XML, rather than proprietary nonsense. More than that, not only does sub-surface allow me to edit the date of a dive in increments greater than 7, I can edit _multiple_ dives at the same time. It's the future. I can't help but feel that this is a sort of digital vagrancy. SubSurface seems great now, but what about in 3 years? 10 years? I know there's a trend of web-based [dive-logs](https://en.divelogs.de/), but I don't want to have to shuffle around, converting what has no business being anything but XML or a CSV to bunch of proprietary, uninterpretable file formats. Having been burnt by SmartTrack, I'm looking for robust export functionality. Luck for me, it seems sub-surface is able to export as CSVs. This seems like a clear candidate to make a stand and own my own data. It's just screaming to be added to the blog. Then if something breaks, it's my own damn fault.
        """)

        self.assertEqual([['wow', 'wow2'], ['wow3']], image_refs)


if __name__ == '__main__':
    unittest.main()
