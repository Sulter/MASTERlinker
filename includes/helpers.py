# Functions that multiple plugins should use
import copy
import json
import logging
import os
import re
import unicodedata


class Plugin:
  def __init__(self, parent):
    self.parent = parent

  def handle_message(self, msg_data):
    pass

  def handle_pm(self, msg_data):
    '''
    By default, treat private messages the same as channel messages.
    '''
    self.handle_message(msg_data)


def parse_config(filename, default):
  config = copy.copy(default)
  try:
    with open(filename) as configfile:
      loaded_config = json.load(configfile)
      # Need to prevent nested dict from being overwritten with an incomplete dict
      for k, v in loaded_config.items():
        if k not in config:
          continue
        if type(v) is dict:
          config[k].update(v)
        else:
          config[k] = v
  except IOError:
    # Will just use the default config
    # and create the file for manual editing
    save_config(config, filename)
  except ValueError:
    # There's a syntax error in the config file
    errorString = "Erroneous config %s requires manual fixing or deletion to proceed." % filename
    logging.error(errorString)
    raise BaseException(errorString)
  return config

def save_config(config_dict, filename):
  path = os.path.dirname(filename)
  if path == '':
    path = './'
  if not os.path.isdir(path):
    os.mkdir(path)

  with open(filename, 'wb') as configfile:
    configfile.write(json.dumps(config_dict, sort_keys=True, indent=2, separators=(',', ': ')).encode('utf-8'))

def time_string(tdel):
  if tdel.days > 14:
    return "{}w ago".format(tdel.days//7)
  elif tdel.days > 1:
    return "{}d ago".format(tdel.days)
  elif tdel.days == 1 or tdel.seconds > 7200:
    return "{}h ago".format((tdel.days*24)+(tdel.seconds//3600))
  elif tdel.seconds > 120:
    return "{}m ago".format(tdel.seconds//60)
  else:
    return "{}s ago".format(tdel.seconds)

def sanitise_string(string):
  '''
  Remove troublesome characters from a string, leaving only readable ones.

  Following unicode categories are unwanted:
    Cc = Other, control
    Cf = Other, format
    Cs = Other, surrogate
    Co = Other, private use
    Cn = Other, not assigned (including noncharacters)
  Following should be replaced with standard spaces
    Zs = Separator, space
    Zl = Separator, line
    Zp = Separator, paragraph
  '''
  string = re.sub('(\x03(\d{1,2}(,\d{1,2})?)?)', '', string)  # Strip IRC color coding
  msg_list = []
  for c in string:
    category = unicodedata.category(c)[0]  # First letter is enough to judge
    if category == 'C':
      continue  # Filthy nonprintable!
    elif category == 'Z':
      msg_list.append(' ')
    else:
      msg_list.append(c)
  return ''.join(msg_list)

SI_large_prefixes = {  # Extend if necessary
  3: 'k',
  6: 'M',
  9: 'G',
  12: 'T',
  15: 'P',
  18: 'E',
}

def shorten_number(number, max_width, engineering=False, include_letter=True, include_minus=True):
  '''
  Return a nice shortened string of a number using SI prefixes. Large numbers only for now (no negative exponents).
  Num is treated as a string instead of taking a numeric approach.
  engineering: use the SI prefix as the decimal symbol to save a character. (e.g. 4k20 instead of 4.20k)
  include_letter: include letters and decimal points in the max width
  '''
  max_width = max(max_width, 3)
  number = str(number)
  if number[0] == '-':
    num = number[1:]
    neg = True
    if include_minus:
      max_width -= 1
  else:
    num = number
    neg = False
  width = len(num)
  if width <= max_width:
    return number

  if include_letter:  # Make room
    if engineering:
      max_width -= 1
    else:
      max_width -= 2
  max_width = max(max_width, 1)

  unit = ((width-1)//3)*3
  dec_point = width - unit
  if engineering:
    output = num[:dec_point] + SI_large_prefixes[unit] + num[dec_point:max_width]
  else:
    output = num[:dec_point] +  '.' + num[dec_point:max_width] + SI_large_prefixes[unit]

  if neg:
    output = '-' + output
  return output

def shorten_period(string, max_terms=2, collapse_weeks=True):
  '''
  Take an ISO 8601 period string, return something human readable.
  Lowercase the time component while leaving the date component uppercase.
  '''
  if string[0] != 'P':
    raise ValueError('Given string is not an ISO 8601 period string')
  datestr, timestr = string[1:].split('T')  # M can be Month or Minute depending on location, so split the time component out
  date_components = re.findall('(\d+[YMWD])', datestr)
  time_components = re.findall('(\d+[hms])', timestr.lower())

  if collapse_weeks:
    new_date = []
    weeks = 0
    for d in date_components:
      if d[-1] == 'W':
        weeks = int(d[:-1])
      elif d[-1] == 'D':
        new_date.append('{}D'.format(int(d[:-1])+(7*weeks)))
      else:
        new_date.append(d)
    date_components = new_date
  components = date_components + time_components
  return ''.join(components[:max_terms])
