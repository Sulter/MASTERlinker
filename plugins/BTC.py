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
      'preferred_nick': 'BitcoinServ',
    }
    self.config = helpers.parse_config('settings_btc.json', default_config)
    self.preferred_nick = parent.add_pseudouser(self.config['preferred_nick'])
    self.last_request = 0
    self.last_black_request = 0
    self.scalefactor = 1.0

  def handle_pm(self, msg_data):
    pass

  def handle_message(self, msg_data):
    if msg_data['message'].lower().startswith('!btc'):
      current_time = time.time()
      currency = 'USD'
      if msg_data['nick'] in self.config['whitelist']:
        cooldown = 0
      elif msg_data['nick'] in self.config['blacklist']:
        if current_time > self.last_black_request + self.config['cooldown_black']:
          self.last_black_request = current_time
          self.send_msg(msg_data['channel'], '{}, you are not a day trader. Go back to your real job.'.format(msg_data['nick']))
      elif msg_data['nick'] in self.config['brownlist']:
        cooldown = self.config['cooldown_brown']
      else:
        cooldown = self.config['cooldown']
      if current_time > self.last_request + cooldown:
        self.last_request = current_time
        thread = threading.Thread(target=self.get_price, args=(msg_data,))
        thread.start()
        #price_str = self.get_price(currency)
        #self.send_msg(msg_data['channel'], price_str)

  def get_price(self, msg_data, currency='USD'):
    today = datetime.date.today()
    d_ago = today - datetime.timedelta(days=1)
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)

    coindesk_current_api = 'https://api.coindesk.com/v1/bpi/currentprice.json'
    coindesk_historical_api = 'https://api.coindesk.com/v1/bpi/historical/close.json'
    coindesk_headers = {'User-Agent': 'Mozilla/5.0'}

    coinbase_api_buy = 'https://api.coinbase.com/v2/prices/BTC-{}/buy'.format(currency)
    coinbase_api_sell = 'https://api.coinbase.com/v2/prices/BTC-{}/sell'.format(currency)

    coindesk_str = None
    coinbase_str = None
    coindesk = 'CoinDesk'
    coinbase = 'Coinbase'

    if currency != 'USD':
      coindesk_str = '{} does not support this currency.'.format(coindesk)
    else:
      try:
        coindesk_current_req = urllib.request.Request(coindesk_current_api, headers=coindesk_headers)
        coindesk_current_data = urllib.request.urlopen(coindesk_current_req).read()
        coindesk_current_json = json.loads(coindesk_current_data.decode('utf-8'))
        coindesk_historical_req = urllib.request.Request(coindesk_historical_api, headers=coindesk_headers)
        coindesk_historical_data = urllib.request.urlopen(coindesk_historical_req).read()
        coindesk_historical_json = json.loads(coindesk_historical_data.decode('utf-8'))
        if d_ago.isoformat() not in coindesk_historical_json['bpi']: #depending on timezone, day might not have changed yet!
          d_ago = d_ago - datetime.timedelta(days=1)
        usd_price_1d = float(coindesk_historical_json['bpi'][d_ago.isoformat()])
        usd_price_1w = float(coindesk_historical_json['bpi'][week_ago.isoformat()])
        usd_price_1m = float(coindesk_historical_json['bpi'][month_ago.isoformat()])
        usd_price = float(coindesk_current_json['bpi']['USD']['rate'].replace(',','')) * self.scalefactor

        d_change = self.format_change(usd_price, usd_price_1d, 'd')
        w_change = self.format_change(usd_price, usd_price_1w, 'w')
        m_change = self.format_change(usd_price, usd_price_1m, 'm')

        coindesk_str = '{}: Spot=${:.2f} {} {} {}'.format(coindesk, usd_price, d_change, w_change, m_change)
      except BaseException as e:
        logging.debug('BTC: CoinDesk request/parse error - {}'.format(e))

    try:
      coinbase_ask_data = urllib.request.urlopen(coinbase_api_buy).read()
      coinbase_bid_data = urllib.request.urlopen(coinbase_api_sell).read()
      coinbase_ask_json = json.loads(coinbase_ask_data.decode('utf-8'))
      coinbase_bid_json = json.loads(coinbase_bid_data.decode('utf-8'))
      coinbase_ask_price = float(coinbase_ask_json['data']['amount']) * self.scalefactor
      coinbase_bid_price = float(coinbase_bid_json['data']['amount']) * self.scalefactor
      coinbase_str = 'BTC/{} - {}: Bid=${} Ask=${}'.format(currency, coinbase, coinbase_bid_price, coinbase_ask_price)
    except BaseException as e:
      logging.debug('BTC: CoinBase request/parse error - {}'.format(e))

    response_strs = [coinbase_str, coindesk_str]
    response_str = ' | '.join([s for s in response_strs if s is not None])
    self.send_msg(msg_data['channel'], response_str)

  def format_change(self, new_price, old_price, char):
    data = {
      'char': char,
      'change': (new_price-old_price)/old_price,
    }
    if data['change'] > 0:
      data['arrow'] = '↑'
      data['color'] = '\x033'
    else:
      data['arrow'] = '↓'
      data['color'] = '\x034'
    return '{color}{char}:{arrow}{change:.2%}'.format(**data)
