import requests

import html2text
import markdown2
__author__ = 'alex'




if __name__ == '__main__':
    entry = get_entry_content('https://kylewm.com/2015/08/you-could-take-another-look-at-your-mf2-e-content')
    # entry = get_entry_content('http://rhiaro.co.uk/2015/08/ilooklikeanengineer')
    # entry = get_entry_content('https://aaronparecki.com/notes/2015/08/03/5/')
    # entry = get_entry_content('https://waterpigs.co.uk/notes/4cMEwe/')
    print entry

    entry = get_entry_content('https://twitter.com/nsaphra/status/1037094009670381568')

    print entry
    # get_entry_content('http://127.0.0.1:5000/e/2015/8/1/things')
