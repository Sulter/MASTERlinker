# Plugin that searches for url links in each message, and sends a message with info about each link.
import includes.helpers as helpers
import re
import urllib
import urllib.parse
from http.cookiejar import CookieJar
#import lxml.html
from bs4 import BeautifulSoup
import json
import logging
import threading
import sqlite3
import time
import datetime
import subprocess


class url_info_finder(helpers.Plugin):
  TLDs = [
    'com',
    'biz',
    'edu',
    'gov',
    'int',
    'mil',
    'moe',
    'net',
    'org',
    'xxx',
    'aero',
    'asia',
    'coop',
    'info',
    'jobs',
    'name',
    'musem',
    'travel',
  ]
  url_regex = re.compile('((https?://|www.)\S+)|(\S+\.([a-z][a-z]|{})\S*)'.format('|'.join(TLDs)), re.IGNORECASE)
  url_prefix = re.compile('(https?://www\.)|(https?://|www\.)', re.IGNORECASE)
  ffprobe_types = [
    'aac',
    'm4a',
    'mkv',
    'mp3',
    'mp4',
    'ogg',
    'wav',
    'flac',
    'opus',
    'webm',
  ]
  ffprobe_regex = re.compile('\.({})\Z'.format('|'.join(ffprobe_types)), re.IGNORECASE)

  def __init__(self, parent):
    super().__init__(parent)
    default_config = {
      'api_keys': {
      'youtube': "Youtube Data API key",
      },
      'ffprobe_enabled': False,
    }
    self.config = helpers.parse_config('settings_url_info_finder.json', default_config)

  def handle_pm(self, msg_data):
    # Ignore private messages, to prevent from flooding/api usage etc.
    pass

  def handle_message(self, msg_data):
    # For each message we start a new thread, because this can be pretty slow (sometimes very slow with dns lookups etc.)
    thread = threading.Thread(target=self.start_thread, args=(msg_data,))
    thread.start()

  def start_thread(self, msg_data):
    # The color code for the message (green), the 0x02 is just a hack
    color = "\x033"
    # If NSFW found in msg, mark it red
    if re.search(r'(nsfw|NSFW)', msg_data["message"]) is not None:
      color = "\x030,4"
    # If NSFL found in msg, mark it other color
    if re.search(r'(nsfl|NSFL)', msg_data["message"]) is not None:
      color = "\x030,6"
    # Find all url links in the message, and send info about them, in one formatted string
    url_info_list = self.parse_msg(msg_data["message"], msg_data["nick"])
    info_string = ' '.join(url_info_list)

    if info_string:
      # Add a nice ending, if the message is too long
      if len(info_string) > 440:
        info_string = info_string[0:440] + "(...)]"
      self.parent.send_msg(msg_data["channel"], '{}{}'.format(color, info_string))

  def search_add_database(self, url, nick):
    '''
    For each url, we add it to the database with time, and increase the counter
    Returns number of times linked, first and last nick to link it
    '''

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
      keylist = ['key', 'total', 'url', 'nick_first', 't1', 'nick_last', 't2']
      data = dict(zip(keylist, entry))
      data['time_first'] = helpers.time_string(datetime.timedelta(seconds=t-data['t1']))
      data['time_last'] = helpers.time_string(datetime.timedelta(seconds=t-data['t2']))
      # Increase counter and add entry
      c.execute("UPDATE URL SET total=?, last_nick=?, last_time=? WHERE url=?", (data['total'] + 1, nick, t, url))
      c.execute("INSERT INTO URLS(url_ID, time) VALUES(?,?)", (c.lastrowid, t))
      conn.commit()

      if data['total'] == 1:
        return " |1: {nick_first} {time_first}".format(**data)
      elif data['nick_first'] == data['nick_last']:
        return " |1: {nick_first} {time_first}, {total}: {time_last}".format(**data)
      else:
        return " |1: {nick_first} {time_first}, {total}: {nick_last} {time_last}".format(**data)
    else:
      # Add to both tables
      c.execute("INSERT INTO URL(total, url, first_nick, first_time, last_nick, last_time) VALUES(?,?,?,?,?,?)", (1, url, nick, t, nick, t))
      c.execute("INSERT INTO URLS(url_ID, time, nick) VALUES(?,?,?)", (c.lastrowid, t, nick))
      conn.commit()
      return ""

  def get_url_info(self, url, ignore_redirects=False):
    if "https://" not in url and "http://" not in url:
      url = "http://" + url

    # Open url
    try:
      cj = CookieJar()
      opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
      opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0')]
      if url == urllib.parse.unquote(url):
        url_safe = urllib.parse.quote(url, safe=":/?=&")
      else:
        url_safe = url
      source = opener.open(url_safe)
      logging.debug("url open:%s", url)
      if url_safe != url:
        logging.debug("url quoted to:%s", url_safe)
    except BaseException as e:
      logging.debug("url_finder error: could not open site - {} - {}".format(url, e))
      raise
      return None, None

    redirect_warning = ""
    rdr_url = source.geturl()
    if rdr_url != url and rdr_url != url_safe and ignore_redirects is False:
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
      return "!potentially malicious! detected content-type: " + detected_file_header[1:4], rdr_url

    return_string = None
    if "html" in header_content_type:  # Resolve normal text type site - get the "title"
      # If it's a normal text/html we just find the title heads, except if it's a youtube video
      if ".youtube." in source.geturl():
        yt = self.yt_info(source.geturl())
        if yt:
          source.close()
          return yt, rdr_url
      elif "github.com" in url:
        git = self.github_info(url)
        if git:
          source.close()
          return git, rdr_url
      return_string = self.get_title(source, url)
    elif self.config['ffprobe_enabled']:
      if re.search(self.ffprobe_regex, url):
        return_string = self.ffprobe_info(url)

    if return_string:
      return_string = return_string.strip()
      source.close()
      return redirect_warning + return_string, rdr_url

    # Fall through: Other types, just show the content type and content length (if any!)
    return_string = source.info().get("Content-type")
    if source.info().get("Content-Length") is not None:
      return_string = return_string + " |  " + str(
        helpers.bytestring(int(source.info().get("Content-Length"))))
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

  def ffprobe_info(self, url):
    '''
    Get title and duration info of media files
    '''
    try:
      proc = subprocess.Popen(['ffprobe', '-v', 'quiet', '-of', 'json', '-show_format', '-show_streams', url], shell=False, stdout=subprocess.PIPE)
      procout = proc.communicate()[0].strip().decode('utf-8')
      media = json.loads(procout)
    except BaseException as e:
      logging.error('ffprobe error - {}'.format(e))
      return
    try:
      # Videos seem to be well behaved on this. Ogg files not so much.
      title = media['format']['tags']['title']
    except:
      # Just case-insensitive search the flat structure, there's too many possibilities.
      try:
        title = re.search('"title": "(.*?)"', procout, re.IGNORECASE)[1]
      except:
        # Just use the filename since everything sucks.
        title = url.split('/')[-1]
        title = urllib.parse.unquote(title)
    return_string = re.sub('\[.*?\]', '', title).strip()

    try:
      duration = helpers.seconds_to_shortened(int(media['format']['duration'].split('.')[0]))
    except:
      duration = None
    try:
      size = helpers.bytestring(int(media['format']['size']))
    except:
      size = None
    metadata = ', '.join(filter(None, [duration, size]))
    if metadata:
      return_string = '{} ({})'.format(return_string, metadata)
    return return_string

  def github_info(self, url):
    result = re.search("(\.com)(/[^ /]+/[^ /]+$)", url)
    if result is None:
      return
    else:
      result = result.group(2)
      api_url = "https://api.github.com/repos" + result
      logging.debug("api url:%s", api_url)
      try:
        result = json.load(urllib.request.urlopen(api_url))
      except:
        logging.debug("url_finder error: github error, either urllib or json fail")
        return

      # Make sure it's a dictionary, otherwise we might not be looking at a repo at all!
      if not isinstance(result, dict):
        return

      return_string = "GitHub| "
      if "name" in result and result["name"]:
        return_string = return_string + result["name"]
      if "description" in result and result["description"]:
        return_string = return_string + " - " + result["description"]
      if "language" in result and result["language"]:
        return_string = return_string + " | >" + result["language"]
      return return_string

  def yt_info(self, url):
    '''
    Uses youtube v3 API to get video info.
    JSON Structure of note:

    items:
      0:
        snippet:
          publishedAt (of form "2017-11-19T01:01:50.000Z")
          channelId, channelTitle, title, description, categoryId
          localized:
            title, description
        contentDetails:
          duration (of form "PT3M18S" (ISO 8601 duration))
        statistics:
          viewCount, likeCount, dislikeCount, favouriteCount, commentCount
    '''
    yt_id = re.search("(\?|\&)v=([a-zA-Z0-9_-]*)", url)

    if yt_id is None:
      return None

    yt_id = yt_id.group()
    if "?v=" in yt_id:
      yt_id = yt_id.partition("?v=")[2]
    elif "&v=" in yt_id:
      yt_id = yt_id.partition("&v=")[2]

    yt_api_key = self.config['api_keys']['youtube']
    api_url = 'https://www.googleapis.com/youtube/v3/videos?id={}&key={}&part=snippet,statistics,contentDetails'.format(yt_id, yt_api_key)
    logging.debug("api url:%s", api_url)

    try:
      req = urllib.request.urlopen(api_url)
      result = json.loads(req.read().decode('utf-8'))
    except BaseException as e:
      logging.debug('url_finder error - json load fail: {}'.format(e))
      return None

    if not result["items"]:
      logging.debug('url_finder error: youtube error, no info on video')
      return None

    item = result["items"][0]
    data = {
      's': item['snippet'],
      'stats': {k: helpers.shorten_number(v, 5) for (k, v) in item['statistics'].items()},
      'duration': helpers.shorten_period(item['contentDetails']['duration']),
    }
    return "(You)Tube: {s[channelTitle]} - {s[title]} ({duration}, {stats[viewCount]} views)".format(**data)

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
      # Hacky fix for utf-8 titles not being detected
      #string = str(t.find(".//title").text.encode('latin1'), 'utf-8')
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
        titlestr = helpers.sanitise_string(info).strip()  # Sanitise first since that will convert unicode whitespace
        # Add info about number of times linked
        info = '[{}{}]'.format(titlestr, self.search_add_database(url, nick))

        if len(info) > 150:
          info = info[0:150]
          info += "(...)]"

        url_info_list.append(info)
    return url_info_list
