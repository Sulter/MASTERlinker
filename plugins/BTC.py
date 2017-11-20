# A plugin for allowing people who are not daytraders to spam the channel with bitcoin prices.
import includes.helpers as helpers
import datetime
import logging
import json
import urllib.request
import time
import threading  # Stopgap solution


class BTC(helpers.Plugin):
  def __init__(self, parent):
    super().__init__(parent)
    default_config = {
      'cooldown': 60*10,  # cooldown time for requests in sec
      'cooldown_brown': 60*30,  # cooldown for people who need to get a life
      'cooldown_black': 15,  # cooldown for telling people they are not daytraders
      'whitelist': [],
      'blacklist': [],
      'brownlist': [],
    }
    self.config = helpers.parse_config('settings_btc.json', default_config)
    self.last_request = 0
    self.last_black_request = 0

  def handle_pm(self, msg_data):
    pass

  def handle_message(self, msg_data):
    if msg_data['message'].lower().startswith("!btc"):
      current_time = time.time()
      currency = 'USD'
      if msg_data['nick'] in self.config['whitelist']:
        cooldown = 0
      elif msg_data['nick'] in self.config['blacklist']:
        if current_time > self.last_black_request + self.config['cooldown_black']:
          self.last_black_request = current_time
          self.parent.send_msg(msg_data['channel'], "{}, you are not a day trader. Go back to your real job.".format(msg_data['nick']))
      elif msg_data['nick'] in self.config['brownlist']:
        cooldown = self.config['cooldown_brown']
      else:
        cooldown = self.config['cooldown']
      if current_time > self.last_request + cooldown:
        self.last_request = current_time
        thread = threading.Thread(target=self.get_price, args=(msg_data,))
        thread.start()
        #price_str = self.get_price(currency)
        #self.parent.send_msg(msg_data['channel'], price_str)

  def get_price(self, msg_data, currency="USD"):
    today = datetime.date.today()
    d_ago = today - datetime.timedelta(days=1)
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)

    current_api = "https://api.coindesk.com/v1/bpi/currentprice.json"
    lastM_api = "https://api.coindesk.com/v1/bpi/historical/close.json"
    coinbase_api_buy = "https://api.coinbase.com/v2/prices/BTC-{}/buy".format(currency)
    coinbase_api_sell = "https://api.coinbase.com/v2/prices/BTC-{}/sell".format(currency)
    try:
      current_r = urllib.request.urlopen(current_api).read()
      lastM_r = urllib.request.urlopen(lastM_api).read()
      coinbase_ask_r = urllib.request.urlopen(coinbase_api_buy).read()
      coinbase_bid_r = urllib.request.urlopen(coinbase_api_sell).read()
      current_j = json.loads(current_r.decode('utf-8'))
      lastM_j = json.loads(lastM_r.decode('utf-8'))
      coinbase_ask_j = json.loads(coinbase_ask_r.decode('utf-8'))
      coinbase_bid_j = json.loads(coinbase_bid_r.decode('utf-8'))
      if d_ago.isoformat() not in lastM_j["bpi"]: #depending on timezone, day might not have changed yet!
        d_ago = d_ago - datetime.timedelta(days=1)
      usd_price_1d = float(lastM_j["bpi"][d_ago.isoformat()])
      usd_price_1w = float(lastM_j["bpi"][week_ago.isoformat()])
      usd_price_1m = float(lastM_j["bpi"][month_ago.isoformat()])

      usd_price = float(current_j["bpi"]["USD"]["rate"].replace(',',''))
      coinbase_ask_price = float(coinbase_ask_j["data"]["amount"])
      coinbase_bid_price = float(coinbase_bid_j["data"]["amount"])
    except BaseException as e:
      logging.debug('BTC: request/parse error - {}'.format(e))
      return ""

    d_change = self.format_change(usd_price, usd_price_1d, 'd')
    w_change = self.format_change(usd_price, usd_price_1w, 'w')
    m_change = self.format_change(usd_price, usd_price_1m, 'm')
    if currency == "USD":
      response_str = "BTC/USD - Coinbase: Bid=${:.2f} Ask=${:.2f} | CoinDesk: Spot=${:.2f} {} {} {}".format(coinbase_bid_price, coinbase_ask_price, usd_price, d_change, w_change, m_change)
    else:
      response_str = "BTC/{} - Coinbase: Bid=${} Ask=${} | CoinDesk does not support this currency.".format(currency, coinbase_bid_price, coinbase_ask_price)
    #return response_str
    self.parent.send_msg(msg_data['channel'], response_str)

  def format_change(self, new_price, old_price, char):
    data = {
      'char': char,
      'change': (new_price-old_price)/old_price,
    }
    if data['change'] > 0:
      data['arrow'] = "↑"
      data['color'] = "\x033"
    else:
      data['arrow'] = "↓"
      data['color'] = "\x034"
    return '{color}{char}:{arrow}{change:.2%}'.format(**data)

#“Powered by (((CoinDesk)))”
