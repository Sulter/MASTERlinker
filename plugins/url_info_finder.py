#this plugin searches for url links in each message, and sends a message with
#info about each link.

import re
import urllib2
from cookielib import CookieJar
import lxml.html
import simplejson
import logging
import settings
import threading
import sqlite3
import time

class url_info_finder():
    
    def url_info_finder(self, main_ref, msg_info):
        #we block private msg, to prevent from flooding/api usage etc.
        if msg_info["channel"] == settings.NICK:
            return None

        #for each message we start a new thread, because this can be pretty slow (sometimes very slow with dns lookups etc.)
        thread = threading.Thread(target = self.start_thread, args=(main_ref, msg_info))
        thread.start()

    def start_thread(self, main_ref, msg_info):
        #Find all url links in the message, and send info about them, in one formatted string
        info_string = ""
        url_info_list = self.parse_msg(msg_info["message"])
        for i, url_info in enumerate(url_info_list):
            info_string = info_string + url_info
            if i != len(url_info_list)-1:
                info_string = info_string + "\x0F  ...  "
        
        if info_string:
            #add a nice ending, if the message is too long
            if len(info_string) > 440:
                info_string[0:440]
                info_string = info_string + "(...)]"
            main_ref.send_msg(msg_info["channel"], info_string) 

    def search_add_database(self, url):
        #for each url, we add it to the database with time, and increase the counter
        #returns number of times linked
        
        #we replace the usual prefix
        url = url.replace("www.", "", 1)
        url = url.replace("http://", "", 1)
        url = url.replace("https://", "", 1)

        print "we add url: " + url
        
        conn = sqlite3.connect(settings.url_sqlite3_db)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS URL (id INTEGER PRIMARY KEY, total INTEGER, url TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS URLS (id INTEGER PRIMARY KEY, url_ID INTEGER, time INTEGER)")

        #find url if already in dbe
        c.execute('SELECT * FROM URL WHERE url=?', (url,))
        entry = c.fetchone()

        if entry:
            #increase counter and add entry
            c.execute("UPDATE URL SET total=? WHERE url=?", (entry[1]+1, url))
            c.execute("INSERT INTO URLS(url_ID, time) VALUES(?,?)", (c.lastrowid, int(time.time()) ))

            conn.commit()
            return " |l:" + str(entry[1])

        else:
            #add to both tables
            c.execute("INSERT INTO URL(total, url) VALUES(?,?)", (1, url))
            c.execute("INSERT INTO URLS(url_ID, time) VALUES(?,?)", (c.lastrowid, int(time.time()) ))

            conn.commit()
            return ""

    def bytestring(self, n):
        tiers = ['B', 'KB', 'MB', 'GB']
        i     = 0
        while n >= 1024 and i < len(tiers):
            n    = n / 1024
            i += 1
        return "{:.0f}".format(n) + tiers[i]

    def get_url_info(self, url, ignore_redirects = False):

        #add http:// to www.-only links
        if "https://" not in url:
            if "http://" not in url:
                url = "http://" + url
                
        #open url
        try:
            cj = CookieJar()
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
            opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0')]
            source = opener.open(url)
            logging.debug("url open:%s", url)
        except:
            logging.debug("url_finder error: could not open site - %s", url)
            return None
        
        redirect_warning = ""
        if source.geturl() != url and ignore_redirects is False:
            redirect_warning = "|REDIRECT| "
            
        #remove the "/" ending, if any
        url = url.rstrip("/")
        
        #looking into the header
        try:
            header_content_type = source.info().getheader("Content-type")
        except: 
            logging.debug("url_finder error: header - invalid. url: %s", url)
            source.close()
            return None
        
        if not header_content_type: 
            detected_file_header = source.read(4)
            source.close()
            return "!this webserver might be malicious! detected content-type: " + detected_file_header[1:4]
                    
        if "html" in header_content_type: #resolve normal text type site - get the "title"
            #if it's a normal text/html we just find the title heads, except if it's a youtube video
            #needs cleaning up!
            if ".youtube." in source.geturl():
                yt = self.yt_info(source.geturl())
                if yt is None:
                    return_string = self.get_title(source, url)
                else:
                    source.close()
                    return yt

            elif "github.com" in url:
                git = self.github_info(url)
                if git is None:
                    return_string = self.get_title(source, url)
                else:
                    source.close()
                    return git
            else:
                return_string = self.get_title(source, url)
           
            if return_string is not None:
                return_string = (return_string.lstrip()).rstrip()  
                source.close()
                return redirect_warning + return_string
            else:
                source.close()
                return None

        else: #other types, just show the content type and content lenght (if any!)
            return_string =  source.info().getheader("Content-type")
            if source.info().getheader("Content-Length") is not None:
                return_string = return_string + " |  " + str(self.bytestring(int(source.info().getheader("Content-Length"))))
            #check for imgur
            if "i.imgur.com" in url: #we check the title of the album
                rex = '(.gif|.png|.jpeg|.img|.jpg|.bmp)\Z'  #common image formats, search at end of string
                search_res = re.search(rex, url)
                if search_res: #only if it is formatted the way we expect (with one of the image formats at the end) (I should probably use the imgur api instead though)
                    new_url = url.rstrip(search_res.group())
                    img_title = self.get_url_info(new_url, True)
                    if img_title is not None:
                        return_string = (img_title.lstrip()).rstrip() + " | " + return_string
            source.close()
            return redirect_warning + return_string

    def github_info(self, url):
        result = re.search("(\.com)(/[^ /]+/[^ /]+$)", url)
        if result is not None:
            result = result.group(2)
            api_url = "https://api.github.com/repos" + result
            logging.debug("api url:%s", api_url)
            try:
                result = simplejson.load(urllib2.urlopen(api_url))
            except:
                logging.debug("url_finder error: github error, either urllib or simplejson fail")
                return None
            
            #make sure it's a dictionary, otherwise we might not be looking at a repo at all!
            if not isinstance(result, dict):
                return None
            
            return_string = "|GITHUB| "
            if "name" in result and result["name"]:
                return_string = return_string + result["name"]
            if "description" in result and result["description"]:
                return_string = return_string + " - " + result["description"]
            if "language" in result and result["language"]:
                return_string = return_string + " | >" + result["language"]
    
            return return_string
        else:
            return None

    def yt_info(self, url):
        yt_ID =  re.search("(\?|\&)v=([a-zA-Z0-9_-]*)", url)
        
        if yt_ID is None:
             return None

        yt_ID = yt_ID.group()
        if "?v=" in yt_ID:
            yt_ID = yt_ID.partition("?v=")[2]
        elif "&v=" in yt_ID:
            yt_ID = yt_ID.partition("&v=")[2]
        
        yt_api_key = settings.yt_api_key
        yt_string_start = "https://www.googleapis.com/youtube/v3/videos?id="
        yt_string_end = "&part=snippet,statistics,contentDetails"
        api_url = yt_string_start + yt_ID + "&key=" + yt_api_key + yt_string_end

        logging.debug("api url:%s", api_url)

        try:
           result = simplejson.load(urllib2.urlopen(api_url))
        except:
            logging.debug("url_finder error: youtube error, either urllib or simplejson fail")
            return None
    
        if not result["items"]:
            logging.debug("url_finder error: youtube error, no info on video")
            return None

        l = result["items"][0]
        stats = l["statistics"]
        details = l["contentDetails"]
        snippet = l["snippet"]
    
        title = snippet["title"]
        duration = (details["duration"].replace("PT", "")).lower()
        views =  stats["viewCount"]
        dislikes = stats["dislikeCount"]
        likes = stats["likeCount"]
        comments = stats["commentCount"]
        return "|YOUTUBE| " + title + " | " + duration +" |"  # additional info, not in use views: " + views +" | d: " + dislikes +" l: " + likes +" | comments: " + comments

    def get_title(self, source, url):

        #get the html
        try:
            t = lxml.html.fromstring(source.read(131072)) #make sure it won't load more then that, because then we might run out of memory
        except:
            logging.debug("url_finder error: couldn't parse with lxml")
            return None
        
        try:
            string = t.find(".//title").text
        except:
            logging.debug("url_finder error: didn't find title tags")
            return None            

        return string

    def find_urls(self, text):
        URL_REGEX = "((http://|https://|www.)\S+)|(\S+\.(com|([a-z][a-z]|biz|gov|info|mil|net|org|name|edu|coop|aero|musem|asia|int|xxx|jobs|travel))\S*)"
        url_array = []
        for url in re.findall(URL_REGEX, text):
            if url[0]:
                url_array.append(url[0]) #if starts with http https or www
            elif url[2]:
                url_array.append(url[2]) #if a other type of link
        return url_array

    def parse_msg(self, msg):
        url_info = []
        #first we search it for links, if any found, send message with info about them, if any
        for url in self.find_urls(msg):
            info =  self.get_url_info(url)
            #we encode into utf-8
            try:
                info = info.encode('utf-8')
            except:
                logging.debug("url_finder error: couldn't parse with lxml")
                info = None
            if info is not None:
                #add info about number of times linked
                info = info + self.search_add_database(url)
                #add a pracet at the beginning and end
                info = "[" + info + "]"
                #the color code for the message (green), the 0x02 is just a hack
                color = "\x033"
                #if NSFW found in msg, mark it red
                if re.search(r'(nsfw|NSFW)', msg) is not None:
                    color = "\x030,4"
                #if NSFL found in msg, mark it other color
                if re.search(r'(nsfl|NSFL)', msg) is not None:
                    color = "\x030,6"
                #sanitizing the message
                #remove newlines etc.
                forbidden = ["\n", "\r", "\t", "\f", "\v"]
                for i in forbidden:
                    info = info.replace(i, " ")

                #remove any empty start
                info = info.lstrip()
                #make sure it isn't longer then 150, if it is, add a nice ending
                if len(info) > 150:
                    info = info[0:150]
                    info = info + "(...)]"

                info_message = '%s%s' % (color, info)
                url_info.append(info_message)

        return url_info
