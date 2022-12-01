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
import random
import html
import codecs
import requests


ESCAPE_SEQUENCE_RE = re.compile(r'''
  ( \\U........      # 8-digit hex escapes
  | \\u....          # 4-digit hex escapes
  | \\x..            # 2-digit hex escapes
  | \\[0-7]{1,3}     # Octal escapes
  | \\N\{[^}]+\}     # Unicode characters by name
  | \\[\\'"abfnrtv]  # Single-character escapes
  )''', re.UNICODE | re.VERBOSE)

def decode_escapes(s):
  def decode_match(match):
    return codecs.decode(match.group(0), 'unicode-escape')
  return ESCAPE_SEQUENCE_RE.sub(decode_match, s)

def ufeff_nick(nick):
  if len(nick) > 1:
    return nick[0] + '\ufeff' + nick[1:]
  return nick

def get_ytid(url):
  domain, _, params = url.partition('/')
  if domain == 'youtu.be':
    return params.partition('?')[0]
  elif domain in ['youtube.com', 'm.youtube.com']:
    yt_id = re.search("(\?|\&)v=([a-zA-Z0-9_-]*)", url)
    if yt_id is None:
      return None
    yt_id = yt_id.group()
    if '?v=' in yt_id:
      yt_id = yt_id.partition("?v=")[2]
    elif '&v=' in yt_id:
      yt_id = yt_id.partition("&v=")[2]
    return yt_id
  return None



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
  reddit_regex = re.compile('reddit.com', re.IGNORECASE)
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

  tax_strs = [
    "€{amount:.02f} has been deducted from {nick}'s account.",
    "€{amount:.02f} has been removed from {nick}'s account.",
    "€{amount:.02f} has been abducted from {nick}'s account.",
    "€{amount:.02f} has been confiscated from {nick}'s account.",
    "€{amount:.02f} has been withdrawn from {nick}'s account.",
    "€{amount:.02f} has been taxed from {nick}'s account.",
    "accounts['{nick}'] -= €{amount:.05f}",
    "{nick} just paid €{amount:.02f} in copyright fees.",
    "{nick} paid €{amount:.02f} in copyright fees.",
  ]

  def __init__(self, parent):
    super().__init__(parent)
    default_config = {
      'api_keys': {
      'youtube': "Youtube Data API key",
      },
      'ffprobe_enabled': False,
      'europeans': (),
      'taxed_memes': ('pog.*', '.*pepe.*', '.*monka.*', 'based', 'redpilled', 'dabs?', 'reee*?', 'gottem', 'nintendo'),
      'taxrate_memes': 1.0,
      'taxrate_links': 0.0,
      'format_link': '\x033',
      'format_nsfw': '\x030,4',
      'format_nsfl': '\x030,6',
      'format_eurotax': '\x038,1',
    }
    self.config = helpers.parse_config('settings_url_info_finder.json', default_config)
    self.tax_regex = re.compile('\\b({})\\b'.format('|'.join(self.config['taxed_memes'])), re.IGNORECASE)
    random.seed()

  def handle_pm(self, msg_data):
    if msg_data['message'].lower().startswith('!reload'):
      self.config = helpers.parse_config('settings_btc.json', self.default_config)
      self.tax_regex = re.compile('\\b({})\\b'.format('|'.join()), re.IGNORECASE)
    # Ignore private messages, to prevent from flooding/api usage etc.
    pass

  def handle_message(self, msg_data):
    # For each message we start a new thread, because this can be pretty slow (sometimes very slow with dns lookups etc.)
    thread = threading.Thread(target=self.start_thread, args=(msg_data,))
    thread.start()

  def start_thread(self, msg_data):
    # Determine if user needs to be taxed
    taxable = msg_data['nick'].lower() in self.config['europeans']
    # The color code for the message (green)
    color = self.config['format_link']
    # If NSFW found in msg, mark it red
    if re.search(r'(nsfw|NSFW)', msg_data["message"]) is not None:
      color = self.config['format_nsfw']
    # If NSFL found in msg, mark it other color
    if re.search(r'(nsfl|NSFL)', msg_data["message"]) is not None:
      color = self.config['format_nsfl']
    # Find all url links in the message, and send info about them, in one formatted string
    url_info_list = self.parse_msg(msg_data["message"], msg_data["nick"])
    info_string = ' '.join(url_info_list)

    tax = 0
    if taxable:
      try:
        memes = len(re.findall(self.tax_regex, msg_data['message']))
        links = len(url_info_list)
        tax = (memes*self.config['taxrate_memes'] + links*self.config['taxrate_links']) * random.uniform(0.95, 1.5)
      except BaseException as e:
        logging.debug('Taxation problem: {}'.format(e))

    if info_string:
      try:
        tax_str = ''
        max_len = 440
        if tax > 0.5:
          nick = msg_data['nick'][:2] + '\ufeff' + msg_data['nick'][2:]
          tax_str = ' ' + self.config['format_eurotax'] + random.choice(self.tax_strs).format(amount=tax, nick=nick)
          max_len -= len(tax_str)
        # Add a nice ending, if the message is too long
        if len(info_string) > max_len:
          info_string = info_string[0:max_len] + "(...)]"
        self.parent.send_msg(msg_data["channel"], '{}{}{}'.format(color, info_string, tax_str))
      except BaseException as e:
        logging.debug('Taxation message problem: {}'.format(e))

  def search_add_database(self, url, nick):
    '''
    For each url, we add it to the database with time, and increase the counter
    Returns number of times linked, first and last nick to link it
    '''

    # We replace the usual prefix, and lowercase the hostname part
    url = self.url_prefix.sub("", url, 1)
    hostname, *tail = url.split("/", 1) + [""]  # Guarantees that tail will contain a non-empty list
    url = "{}/{}".format(hostname.lower(), tail[0])
    
    # Youtube video ID matching
    ytid = get_ytid(url)
    if ytid:
      url = 'YOUTUBE_VIDEO_ID_' + ytid

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

      data['nick_first'] = ufeff_nick(data['nick_first'])
      data['nick_last'] = ufeff_nick(data['nick_last'])

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
      #opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:58.0) Gecko/20100101 Firefox/58.0')]
      opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0')]
      if url == urllib.parse.unquote(url):
        url_safe = urllib.parse.quote(url, safe=":/?=&@")
      else:
        url_safe = url
      if url_safe != url:
        logging.debug("url quoted to:%s", url_safe)
      source = opener.open(url_safe)
      logging.debug("url open:%s", url)
    except BaseException as e:
      logging.debug("url_finder error: could not open site - {} - {}".format(url, e))
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
      elif "twitter.com" in url:
        tw = self.twitter_info(url)
        if tw:
          source.close()
          return tw, rdr_url
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
        #result = json.load(urllib.request.urlopen(api_url))
        result = requests.get(api_url).json()
      except:
        #logging.debug("url_finder error: github error, either urllib or json fail")
        logging.debug('url_finder error: github error, requests fail')
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
      logging.error('url_finder error - json load fail: {}'.format(e))
      return None

    try:
      if not result['items']:
        logging.error('url_finder error: youtube error, no info on video')
        return None

      item = result['items'][0]
      data = {
        's': item['snippet'],
        'stats': {k: helpers.shorten_number(v, 5) for (k, v) in item['statistics'].items()},
        'duration': helpers.shorten_period(item['contentDetails']['duration']),
      }
      info = "(You)Tube: {s[channelTitle]} - {s[title]} ({duration}, {stats[viewCount]} views)".format(**data)
      logging.debug('url_finder: YT info is {}'.format(info))
      return info
    except BaseException as e:
      logging.error('url_finder error - parse fail: {}'.format(e))

  def twitter_info(self, url):
    # We have to use oembed API because twitter is forcing JS on regular pages and auth on other APIs
    # HTML regex: "html":"(.*?[^\\])"
    logging.debug("Attempting to decode twitter link")
    api_url = 'https://publish.twitter.com/oembed?url=' + url
    logging.debug("api url:%s", api_url)

    try:
      req = urllib.request.urlopen(api_url)
      twdata = req.read().decode('utf8')
      logging.debug('Twitter API returned: ' + twdata)
      return_str = ' '.join(re.findall(r'\\u003E(.*?)\\u003C', twdata)).strip()
      return_str = html.unescape(return_str).replace(r'\/', '/')
      return_str = decode_escapes(return_str).strip()
    except BaseException as e:
      logging.error('url_finder error - twitter oembed load fail: {}'.format(e))
      return None

    logging.debug('Twitter result string: ' + return_str)
    return return_str

  def get_title(self, source, url):
    # Make sure it won't load more than 131072, because then we might run out of memory
    try:
      #t = lxml.html.fromstring(source.read(131072))
      # BeautifulSoup is seemingly less tolerant, give it 2MB
      # UPDATE: try 4MB since twitter is garbage
      logging.debug("Attempting to read from url: "+url)
      data = source.read(4194304)
      logging.debug("Source read (size {:d}), attempting to parse with BeautifulSoup...".format(len(data)))
      soup = BeautifulSoup(data, 'html.parser')
      #soup = BeautifulSoup(source.read(8388608), 'html.parser')
    except BaseException as e:
      #logging.debug("url_finder error: couldn't parse with lxml")
      logging.debug("url_finder error: couldn't parse with beautifulsoup: " + str(e))
      return None

    try:
      title = soup.find("meta", property="og:title", content=True)
      if title and title["content"]:
        return title["content"]
      logging.debug("url_finder invalid og:title found: " + str(title))
    except:
      logging.debug("url_finder no og:title found: " + str(e))

    try:
      # Hacky fix for utf-8 titles not being detected
      #string = str(t.find(".//title").text.encode('latin1'), 'utf-8')
      return soup.title.string
    except BaseException as e:
      logging.debug("url_finder error: didn't find title tags: " + str(e))
      filename = time.strftime('%Y%m%d-%H%M%S.urldata')
      logging.debug("Dumping to file: " + filename)
      with open(filename, 'wb') as file:
        try:
          file.write(data)
        except BaseException as e:
          logging.debug("Failed to write: " + str(e))
      return None
    #return string

  def find_urls(self, text):
    url_array = []
    for url in re.findall(self.url_regex, text):
      if url[0]:
        url_array.append(url[0])  # if starts with http https or www
      elif url[2]:
        url_array.append(url[2])  # if a other type of link
    if len(re.findall(self.reddit_regex, text)) > 0:  # Reddit go home
      url_array.append('reddit.com')
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

        if len(info) > 425:
          info = info[0:420]
          info += "(...)]"

        url_info_list.append(info)
    return url_info_list
