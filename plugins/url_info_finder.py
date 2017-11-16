# Plugin that searches for url links in each message, and sends a message with info about each link.
import includes.helpers as helpers
import re
import urllib
from http.cookiejar import CookieJar
#import lxml.html
from bs4 import BeautifulSoup
import json
import logging
import threading
import sqlite3
import time
import datetime


class url_info_finder(helpers.Plugin):
  TLDs = [
    "com",
    "biz",
    "edu",
    "gov",
    "int",
    "mil",
    "moe",
    "net",
    "org",
    "xxx",
    "aero",
    "asia",
    "coop",
    "info",
    "jobs",
    "name",
    "musem",
    "travel",
  ]
  url_regex = re.compile("((https?://|www.)\S+)|(\S+\.([a-z][a-z]|" + "|".join(TLDs) + ")\S*)", re.IGNORECASE)
  url_prefix = re.compile("(https?://www\.)|(https?://|www\.)", re.IGNORECASE)

  def handle_pm(self, msg_data):
    # Ignore private messages, to prevent from flooding/api usage etc.
    pass

  def handle_message(self, msg_data):
    # For each message we start a new thread, because this can be pretty slow (sometimes very slow with dns lookups etc.)
    thread = threading.Thread(target=self.start_thread, args=(msg_data,))
    thread.start()

  def start_thread(self, msg_data):
    # Find all url links in the message, and send info about them, in one formatted string
    info_string = ""
    url_info_list = self.parse_msg(msg_data["message"], msg_data["nick"])
    for i, url_info in enumerate(url_info_list):
      info_string = info_string + url_info
      if i != len(url_info_list) - 1:
        info_string = info_string + "\x0F  ...  "

    if info_string:
      # Add a nice ending, if the message is too long
      if len(info_string) > 440:
        info_string[0:440]
        info_string = info_string + "(...)]"
      self.parent.send_msg(msg_data["channel"], info_string)

  def search_add_database(self, url, nick):
    """
    For each url, we add it to the database with time, and increase the counter
    Returns number of times linked, first and last nick to link it
    """

    # We replace the usual prefix, and lowercase the hostname part
    url = self.url_prefix.sub("", url, 1)
    hostname, *tail = url.split("/", 1) + [""]  # Guarantees that tail will contain a non-empty list
    url = "{}/{}".format(hostname.lower(), tail[0])

    logging.debug("we add url: " + url)
    db_path = "database/url_sql3.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # We could just SELECT all instances of the URL to determine nicks and times, but this is a speed vs memory tradeoff
    c.execute("CREATE TABLE IF NOT EXISTS URL (id INTEGER PRIMARY KEY, total INTEGER, url TEXT, first_nick TEXT, first_time INT, last_nick TEXT, last_time INT)")
    c.execute("CREATE TABLE IF NOT EXISTS URLS (id INTEGER PRIMARY KEY, url_ID INTEGER, time INTEGER, nick TEXT)")

    # Find url if already in db
    c.execute('SELECT * FROM URL WHERE url=?', (url,))
    entry = c.fetchone()
    t = int(time.time())

    if entry:
      key, total, url2, first_nick, t1, last_nick, t2, *tmp = entry
      # Increase counter and add entry
      c.execute("UPDATE URL SET total=?, last_nick=?, last_time=? WHERE url=?", (total + 1, nick, t, url))
      c.execute("INSERT INTO URLS(url_ID, time) VALUES(?,?)", (c.lastrowid, t))
      conn.commit()

      time_str_1 = helpers.time_string(datetime.timedelta(seconds=t-t1))
      time_str_2 = helpers.time_string(datetime.timedelta(seconds=t-t2))
      if total == 1:
        return " |1: {} {}".format(first_nick, time_str_1)
      elif first_nick == last_nick:
        return " |1: {} {}, {}: {}".format(first_nick, time_str_1, str(total), time_str_2)
      else:
        return " |1: {} {}, {}: {} {}".format(first_nick, time_str_1, str(total), last_nick, time_str_2)

    else:
      # Add to both tables
      c.execute("INSERT INTO URL(total, url, first_nick, first_time, last_nick, last_time) VALUES(?,?,?,?,?,?)", (1, url, nick, t, nick, t))
      c.execute("INSERT INTO URLS(url_ID, time, nick) VALUES(?,?,?)", (c.lastrowid, t, nick))
      conn.commit()
      return ""

  def bytestring(self, n):
    tiers = ['B', 'KB', 'MB', 'GB']
    i = 0
    while n >= 1024 and i < len(tiers):
      n = n / 1024
      i += 1
    return "{:.0f}".format(n) + tiers[i]

  def get_url_info(self, url, ignore_redirects=False):

    if "https://" not in url and "http://" not in url:
      url = "http://" + url

    # Open url
    try:
      cj = CookieJar()
      opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
      opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0')]
      url_safe = urllib.parse.quote(url, safe=":/?=&")
      source = opener.open(url_safe)
      logging.debug("url open:%s", url)
      if url_safe != url:
        logging.debug("url quoted to:%s", url_safe)
    except:
      logging.debug("url_finder error: could not open site - %s", url)
      raise
      return None, None

    redirect_warning = ""
    rdr_url = source.geturl()
    if rdr_url != url and ignore_redirects is False:
      redirect_warning = "→"

    url = url.rstrip("/")

    try:
      header_content_type = source.info().get("Content-type")
    except:
      logging.debug("url_finder error: header - invalid. url: %s", url)
      source.close()
      return None, rdr_url

    if not header_content_type:
      detected_file_header = source.read(4)
      source.close()
      return "!this webserver might be malicious! detected content-type: " + detected_file_header[1:4], rdr_url

    if "html" in header_content_type:  # Resolve normal text type site - get the "title"
      # If it's a normal text/html we just find the title heads, except if it's a youtube video
      if ".youtube." in source.geturl():
        yt = self.yt_info(source.geturl())
        if yt is None:
          return_string = self.get_title(source, url)
        else:
          source.close()
          return yt, rdr_url

      elif "github.com" in url:
        git = self.github_info(url)
        if git is None:
          return_string = self.get_title(source, url)
        else:
          source.close()
          return git, rdr_url
      else:
        return_string = self.get_title(source, url)

      if return_string is not None:
        return_string = (return_string.lstrip()).rstrip()
        source.close()
        return redirect_warning + return_string, rdr_url
      #else:
        #source.close()
        #return None, rdr_url

    # Fall through: Other types, just show the content type and content length (if any!)
    return_string = source.info().get("Content-type")
    if source.info().get("Content-Length") is not None:
      return_string = return_string + " |  " + str(
        self.bytestring(int(source.info().get("Content-Length"))))
    # Check for imgur
    if "i.imgur.com" in url:  # we check the title of the album
      rex = '(.gif|.png|.jpeg|.img|.jpg|.bmp)\Z'  # common image formats, search at end of string
      search_res = re.search(rex, url)
      if search_res:  # only if it is formatted the way we expect (with one of the image formats at the end) (I should probably use the imgur api instead though)
        new_url = url.rstrip(search_res.group())
        img_title = self.get_url_info(new_url, True)[0]
        if img_title is not None:
          return_string = (img_title.lstrip()).rstrip() + " | " + return_string
    source.close()
    return redirect_warning + return_string, rdr_url

  def github_info(self, url):
    result = re.search("(\.com)(/[^ /]+/[^ /]+$)", url)
    if result is not None:
      result = result.group(2)
      api_url = "https://api.github.com/repos" + result
      logging.debug("api url:%s", api_url)
      try:
        result = json.load(urllib.request.urlopen(api_url))
      except:
        logging.debug("url_finder error: github error, either urllib or json fail")
        return None

      # Make sure it's a dictionary, otherwise we might not be looking at a repo at all!
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
    yt_id = re.search("(\?|\&)v=([a-zA-Z0-9_-]*)", url)

    if yt_id is None:
      return None

    yt_id = yt_id.group()
    if "?v=" in yt_id:
      yt_id = yt_id.partition("?v=")[2]
    elif "&v=" in yt_id:
      yt_id = yt_id.partition("&v=")[2]

    yt_api_key = self.parent.config['api_keys']['youtube']
    yt_string_start = "https://www.googleapis.com/youtube/v3/videos?id="
    yt_string_end = "&part=snippet,statistics,contentDetails"
    api_url = yt_string_start + yt_id + "&key=" + yt_api_key + yt_string_end

    logging.debug("api url:%s", api_url)

    try:
      result = json.load(urllib.request.urlopen(api_url))
    except:
      logging.debug("url_finder error: youtube error, either urllib or json fail")
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
    views = stats["viewCount"]
    dislikes = stats["dislikeCount"]
    likes = stats["likeCount"]
    comments = stats["commentCount"]
    return "|YOUTUBE| " + title + " | " + duration + " | views: " + views + " |"

  def get_title(self, source, url):
    # Make sure it won't load more than 131072, because then we might run out of memory
    try:
      #t = lxml.html.fromstring(source.read(131072))
      # BeautifulSoup is seemingly less tolerant, give it 2MB
      soup = BeautifulSoup(source.read(2097152), 'html.parser')
    except:
      #logging.debug("url_finder error: couldn't parse with lxml")
      logging.debug("url_finder error: couldn't parse with beautifulsoup")
      return None

    try:
      # Hacky fix for utf8 titles not being detected
      #string = str(t.find(".//title").text.encode('latin1'), 'utf8')
      return soup.title.string
    except:
      logging.debug("url_finder error: didn't find title tags")
      return None

    #return string

  def find_urls(self, text):
    url_array = []
    for url in re.findall(self.url_regex, text):
      if url[0]:
        url_array.append(url[0])  # if starts with http https or www
      elif url[2]:
        url_array.append(url[2])  # if a other type of link
    return url_array

  def parse_msg(self, msg, nick):
    url_info_list = []
    # First we search it for links, if any found, send message with info about them, if any
    for url in self.find_urls(msg):
      info, rdr_url = self.get_url_info(url)
      if info is not None:
        # Add info about number of times linked
        info += self.search_add_database(url, nick)
        info = "[" + info + "]"
        # The color code for the message (green), the 0x02 is just a hack
        color = "\x033"
        # If NSFW found in msg, mark it red
        if re.search(r'(nsfw|NSFW)', msg) is not None:
          color = "\x030,4"
        # If NSFL found in msg, mark it other color
        if re.search(r'(nsfl|NSFL)', msg) is not None:
          color = "\x030,6"
        # Sanitizing the message
        forbidden = ["\n", "\r", "\t", "\f", "\v"]
        for i in forbidden:
          info = info.replace(i, " ")

        # Remove any empty start
        info = info.lstrip()
        if len(info) > 150:
          info = info[0:150]
          info += "(...)]"

        info_message = '%s%s' % (color, info)
        url_info_list.append(info_message)
    return url_info_list
