# A plugin for allowing people who are not daytraders to spam the channel with bitcoin prices.
import includes.helpers as helpers
import datetime
import logging
import json
import urllib.request
import time
import threading  # Stopgap solution


class BTC(helpers.Plugin):
  default_config = {
    'cooldown': 60*10,  # cooldown time for requests in sec
    'cooldown_brown': 60*30,  # cooldown for people who need to get a life
    'cooldown_black': 15,  # cooldown for telling people they are not daytraders
    'whitelist': [],
    'blacklist': [],
    'brownlist': [],
    'morg_price': 0,
    'morg_date': '',
  }

  def __init__(self, parent):
    super().__init__(parent)
    self.config = helpers.parse_config('settings_btc.json', self.default_config)
    self.last_request = 0
    self.last_black_request = 0
    self.scalefactor = 1.0

  def handle_pm(self, msg_data):
    if msg_data['message'].lower().startswith('!reload'):
      self.config = helpers.parse_config('settings_btc.json', self.default_config)
    elif msg_data['message'].lower().startswith('!btcfactor'):
      self.scalefactor = float(msg_data['message'][10:])
      print('PM handled, scalefactor = {}'.format(self.scalefactor))
    else:
      print('PM not handled, scalefactor = {}'.format(self.scalefactor))

  def handle_message(self, msg_data):
    if msg_data['message'].lower().startswith('!btc'):
      current_time = time.time()
      currency = 'USD'
      if msg_data['nick'] in self.config['whitelist']:
        cooldown = 0
      elif msg_data['nick'] in self.config['blacklist']:
        if current_time > self.last_black_request + self.config['cooldown_black']:
          self.last_black_request = current_time
          self.parent.send_msg(msg_data['channel'], '{}, this constitutes a taxable event. You have been reported to the relevant taxation office.'.format(msg_data['nick']))
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
    elif msg_data['message'].startswith('$'):
      # https://help.coinbase.com/en/coinbase/getting-started/getting-started-with-coinbase/supported-cryptocurrencies
      supported_coins = {'AAVE', 'ADA', 'ALGO', 'ANKR', 'ATOM', 'BAL', 'BAND', 'BAT', 'BCH', 'BNT', 'BSV', 'BTC', 'CGLD', 'COMP', 'CRV', 'CVC', 'DAI', 'DASH', 'DNT', 'DOGE', 'EOS', 'ETC', 'ETH', 'FIL', 'GRT', 'GNT', 'KNC', 'LINK', 'LOOM', 'LRC', 'LTC', 'MANA', 'MATIC', 'MKR', 'NMR', 'NU', 'OMG', 'OXT', 'REN', 'REP', 'SUSHI', 'SKL', 'SNX', 'STORJ', 'USDC', 'UMA', 'UNI', 'WBTC', 'XLM', 'XRP', 'XTZ', 'YFI', 'ZEC', 'ZRX'}
      coin = msg_data['message'].upper()[1:]
      if coin in supported_coins:
        if msg_data['nick'] in self.config['whitelist']:
          cooldown = 0
        else:
          cooldown = 5
        current_time = time.time()
        if current_time > self.last_request + cooldown:
          logging.debug('BTCv2: coin requested - {}'.format(coin))
          self.last_request = current_time
          thread = threading.Thread(target=self.get_price_v2, args=(msg_data['channel'], coin,))
          thread.start()
        else:
          logging.debug('BTCv2: coin requested but on cooldown - {}'.format(coin))
      else:
        logging.debug('BTCv2: invalid coin - {}'.format(coin))


  def get_price_v2(self, channel, coin, currency='USD'):
    # Only uses Coinbase API, supports all Coinbase coins
    def get_cb_price_num(url):  # Will raise exceptions
      data = urllib.request.urlopen(url, timeout=5).read()
      d_json = json.loads(data.decode('utf-8'))
      return float(d_json['data']['amount'])

    coinbase_api_buy = 'https://api.coinbase.com/v2/prices/{}-{}/buy'.format(coin, currency)
    coinbase_api_sell = 'https://api.coinbase.com/v2/prices/{}-{}/sell'.format(coin, currency)
    coinbase_api_spot = 'https://api.coinbase.com/v2/prices/{}-{}/spot'.format(coin, currency)  # Add ?date=yyyy-mm-dd for historic
    today = datetime.date.today()
    d_ago = today - datetime.timedelta(days=1)
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)
    year_ago = today - datetime.timedelta(days=365)

    coinbase_str = None
    history_str = None
    coinbase = 'Coinbase'

    try:
      coinbase_ask = get_cb_price_num(coinbase_api_buy) * self.scalefactor
      coinbase_bid = get_cb_price_num(coinbase_api_sell) * self.scalefactor
      coinbase_str = '{}/{} - {}: Bid=${:.2f} Ask=${:.2f}'.format(coin, currency, coinbase, coinbase_bid, coinbase_ask)
    except BaseException as e:
      logging.debug('BTCv2: CoinBase buy/sell request/parse error - {}'.format(e))

    try:
      coinbase_spot = get_cb_price_num(coinbase_api_spot) * self.scalefactor
      coinbase_spot_d = get_cb_price_num(coinbase_api_spot+'?date='+d_ago.isoformat())
      coinbase_spot_w = get_cb_price_num(coinbase_api_spot+'?date='+week_ago.isoformat())
      coinbase_spot_m = get_cb_price_num(coinbase_api_spot+'?date='+month_ago.isoformat())
      coinbase_spot_y = get_cb_price_num(coinbase_api_spot+'?date='+year_ago.isoformat())
      d_change = self.format_change(coinbase_spot, coinbase_spot_d, 'd')
      w_change = self.format_change(coinbase_spot, coinbase_spot_w, 'w')
      m_change = self.format_change(coinbase_spot, coinbase_spot_m, 'm')
      y_change = self.format_change(coinbase_spot, coinbase_spot_y, 'y')
      history_str = 'Spot=${:.2f} {} {} {} {}'.format(coinbase_spot, d_change, w_change, m_change, y_change)
    except BaseException as e:
      logging.debug('BTCv2: CoinBase history request/parse error - {}'.format(e))

    response_strs = [coinbase_str, history_str]
    response_str = ' | '.join([s for s in response_strs if s is not None])
    self.parent.send_msg(channel, response_str)


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
        #morg_change = self.format_change(usd_price, self.config['morg_price'], 'Morg')

        coindesk_str = '{}: Spot=${:.2f} {} {} {}'.format(coindesk, usd_price, d_change, w_change, m_change)
        #coindesk_str += ' {} ({})'.format(morg_change, self.config['morg_date'])
      except BaseException as e:
        logging.debug('BTC: CoinDesk request/parse error - {}'.format(e))

    try:
      coinbase_ask_data = urllib.request.urlopen(coinbase_api_buy).read()
      coinbase_bid_data = urllib.request.urlopen(coinbase_api_sell).read()
      coinbase_ask_json = json.loads(coinbase_ask_data.decode('utf-8'))
      coinbase_bid_json = json.loads(coinbase_bid_data.decode('utf-8'))
      coinbase_ask_price = float(coinbase_ask_json['data']['amount']) * self.scalefactor
      coinbase_bid_price = float(coinbase_bid_json['data']['amount']) * self.scalefactor
      coinbase_str = 'BTC/{} - {}: Bid=${:.2f} Ask=${:.2f}'.format(currency, coinbase, coinbase_bid_price, coinbase_ask_price)
    except BaseException as e:
      logging.debug('BTC: CoinBase request/parse error - {}'.format(e))

    response_strs = [coinbase_str, coindesk_str]
    response_str = ' | '.join([s for s in response_strs if s is not None])
    self.parent.send_msg(msg_data['channel'], response_str)

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
