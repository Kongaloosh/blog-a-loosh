from selenium import webdriver
import requests
import datetime
import re
import time
nonce_pattern = re.compile('\'([^\']*)\'')
epoch = datetime.datetime.utcfromtimestamp(0)
driver = None
def unix_time_millis(dt):
    return (dt - epoch).total_seconds() * 1000.0
i = 0
while True:
    try:
        driver = webdriver.Firefox()
        time.sleep(2)
        print i
        url = "https://polldaddy.com/n/6d9963b3e24642ed5f3bd574c0280657/9793268?"+str(int(unix_time_millis(datetime.datetime.now())))
        nonce_request = requests.get(url)
        nonce = re.findall('\'([^\']*)\'', nonce_request.text)[0]

        url = "http://polls.polldaddy.com/vote-js.php?p=9793268&b=0&a=44802685,&o=&va=16&cookie=0&n={0}&url=http%3A//www.radiotimes.com/news/2017-07-21/radio-times-radio-and-podcast-champion-round-4-5".format(nonce)
        driver.get(url)
        if driver.page_source.find("Thank you") == -1:
            print "it's dead"
            print driver.page_source
            time.sleep(10)
        driver.delete_all_cookies()
        # if i%100 == 0:
        #     print "{0} submissions for the tims".format(i)
        i += 1
        driver.close()
    except:
        pass
driver.close()