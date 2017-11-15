# A plugin for allowing people who are not daytraders to spam the channel with bitcoin prices.
import datetime
import logging
import json
import urllib.request
import time
import includes.helpers as helpers


class BTC():
  def __init__(self):
    default_config = {
      'cooldown': 60*10,  # cooldown time for requests in sec
      'cooldown_brown': 60*30,  # cooldown for people who need to get a life
      'cooldown_black': 15,  # cooldown for telling people they are not daytraders
      'whitelist': [],
      'blacklist': [],
      'brownlist': [],
    }
    self.config = helpers.parse_config('btc_settings.json', default_config)
    self.last_request = 0
    self.last_black_request = 0

  def BTC(self, main_ref, msg_info):
    if msg_info['channel'] == main_ref.config['connection']['nick']:
      return None

    if msg_info['message'].lower().startswith("!btc"):
      current_time = time.time()
      currency = 'USD'
      if msg_info['nick'] in self.config['whitelist']:
        cooldown = 0
      elif msg_info['nick'] in self.config['blacklist']:
        if current_time > self.last_black_request + self.config['cooldown_black']:
          self.last_black_request = current_time
          main_ref.send_msg(msg_info['channel'], "{}, you are not a day trader. Go back to your real job.".format(msg_info['nick']))
      elif msg_info['nick'] in self.config['brownlist']:
        cooldown = self.config['cooldown_brown']
      else:
        cooldown = self.config['cooldown']
      if current_time > self.last_request + cooldown:
        self.last_request = current_time
        price_str = self.get_price(currency)
        main_ref.send_msg(msg_info['channel'], price_str)

  def get_price(self, currency="USD"):
    current_api = "https://api.coindesk.com/v1/bpi/currentprice.json"
    lastM_api = "https://api.coindesk.com/v1/bpi/historical/close.json"
    coinbase_api_buy = "https://api.coinbase.com/v2/prices/BTC-{}/buy".format(currency)
    coinbase_api_sell = "https://api.coinbase.com/v2/prices/BTC-{}/sell".format(currency)
    try:
      current_r = urllib.request.urlopen(current_api).read()
      lastM_r = urllib.request.urlopen(lastM_api).read()
      coinbase_buy_r = urllib.request.urlopen(coinbase_api_buy).read()
      coinbase_sell_r = urllib.request.urlopen(coinbase_api_sell).read()
    except urllib.error.HTTPError:
      logging.debug("BTC: couldn't make the request")
      return ""
    try:
      current_j = json.loads(current_r.decode('utf-8'))
      lastM_j = json.loads(lastM_r.decode('utf-8'))
      coinbase_buy_j = json.loads(coinbase_buy_r.decode('utf-8'))
      coinbase_sell_j = json.loads(coinbase_sell_r.decode('utf-8'))
    except:
      logging.debug("BTC: couldn't decode the request")
      return ""

    today = datetime.date.today()
    d_ago = today - datetime.timedelta(days=1)
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)

    try:
      if d_ago.isoformat() not in lastM_j["bpi"]: #depending on timezone, day might not have changed yet!
        d_ago = d_ago - datetime.timedelta(days=1)
      usd_price_1d = lastM_j["bpi"][d_ago.isoformat()]
      usd_price_1w = lastM_j["bpi"][week_ago.isoformat()]
      usd_price_1m = lastM_j["bpi"][month_ago.isoformat()]
    except:
      logging.debug("BTC: api changed or date/time error")
      return ""

    try:
      usd_price = current_j["bpi"]["USD"]["rate"]
      #eur_price = current_j["bpi"]["EUR"]["rate"]
      coinbase_buy_price = coinbase_buy_j["data"]["amount"]
      coinbase_sell_price = coinbase_sell_j["data"]["amount"]
    except:
      logging.debug("BTC: the api probably changed")
      return ""

    d_change = (1 - (float(usd_price.replace(",","")) / float(usd_price_1d))) * -100
    week_change = (1 - (float(usd_price.replace(",","")) / float(usd_price_1w))) * -100
    month_change = (1 - (float(usd_price.replace(",","")) / float(usd_price_1m))) * -100
    if currency == "USD":
      response_str = "BTC/USD - Coinbase: Bid=${} Ask=${} | CoinDesk: Spot=${} {} {} {}".format(coinbase_sell_price, coinbase_buy_price, usd_price.split(".", 1)[0], self.format_change(d_change, "d"), self.format_change(week_change, "w"), self.format_change(month_change, "m"))
    else:
      response_str = "BTC/{} - Coinbase: Bid=${} Ask=${} | CoinDesk does not support this currency.".format(currency, coinbase_sell_price, coinbase_buy_price)
    #response_str = "฿: $" + usd_price.split(".", 1)[0] +  " " + \
    #    self.format_change(d_change, "d") + " " + self.format_change(week_change, "w") + " " + self.format_change(month_change, "m")
    return response_str

  def format_change(self, change, char):
    if change > 0:
      arrow = "↑"
      color = "\x033"
    else:
      arrow = "↓"
      color = "\x034"

    change = color + char + ":" + arrow + str(round(change, 2)) + "%"
    return change

#“Powered by (((CoinDesk)))”
