# Functions that multiple plugins should use
import copy
import json
import logging
import os


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
