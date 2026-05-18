# A plugin for allowing people who are not daytraders to spam the channel with bitcoin prices.
import includes.helpers as helpers
import datetime
import logging
import json
import urllib.request
import urllib.error
import urllib.parse
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
      print(f'PM handled, scalefactor = {self.scalefactor}')
    else:
      print(f'PM not handled, scalefactor = {self.scalefactor}')

  def handle_message(self, msg_data):
    if msg_data['message'].lower().startswith('!btc'):
      current_time = time.time()
      currency = 'USD'
      if msg_data['nick'] in self.config['whitelist']:
        cooldown = 0
      elif msg_data['nick'] in self.config['blacklist']:
        if current_time > self.last_black_request + self.config['cooldown_black']:
          self.last_black_request = current_time
          self.parent.send_msg(msg_data['channel'], f"{msg_data['nick']}, this constitutes a taxable event. You have been reported to the relevant taxation office.")
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
      if msg_data['nick'] in self.config['whitelist']:
        cooldown = 0
      else:
        cooldown = 5
      current_time = time.time()
      if current_time < self.last_request + cooldown:
        logging.debug('Finance: request on cooldown')
        return

      query = msg_data['message'].upper()[1:]

      # https://help.coinbase.com/en/coinbase/getting-started/getting-started-with-coinbase/supported-cryptocurrencies
      supported_coins = {'AAVE', 'ADA', 'ALGO', 'ANKR', 'ATOM', 'BAL', 'BAND', 'BAT', 'BCH', 'BNT', 'BSV', 'BTC', 'CGLD', 'COMP', 'CRV', 'CVC', 'DAI', 'DASH', 'DNT', 'DOGE', 'EOS', 'ETC', 'ETH', 'FIL', 'GRT', 'GNT', 'KNC', 'LINK', 'LOOM', 'LRC', 'LTC', 'MANA', 'MATIC', 'MKR', 'NMR', 'NU', 'OMG', 'OXT', 'REN', 'REP', 'SUSHI', 'SKL', 'SNX', 'STORJ', 'USDC', 'UMA', 'UNI', 'WBTC', 'XLM', 'XRP', 'XTZ', 'YFI', 'ZEC', 'ZRX'}

      if query in supported_coins:
        logging.debug(f'BTCv2: coin requested - {query}')
        self.last_request = current_time
        thread = threading.Thread(target=self.get_price_v2, args=(msg_data['channel'], query,))
        thread.start()
        return

      # If not a crypto coin, try forex or stock
      self.last_request = current_time
      thread = threading.Thread(target=self.get_finance_price, args=(msg_data['channel'], query,))
      thread.start()

  def get_finance_price(self, channel, query, max_len=430):
    query = query.replace('/', ':')
    parts = query.split(':')
    base = parts[0].upper()
    quote = ''
    if len(parts) > 1 and parts[1]:
      quote = parts[1].upper()

    forex_currencies = {'AED', 'AFN', 'ALL', 'AMD', 'ANG', 'AOA', 'ARS', 'AUD', 'AWG', 'AZN', 'BAM', 'BBD', 'BDT', 'BGN', 'BHD', 'BIF', 'BMD', 'BND', 'BOB', 'BRL', 'BSD', 'BTC', 'BTN', 'BWP', 'BYN', 'BZD', 'CAD', 'CDF', 'CHF', 'CLF', 'CLP', 'CNH', 'CNY', 'COP', 'CRC', 'CUC', 'CUP', 'CVE', 'CZK', 'DJF', 'DKK', 'DOP', 'DZD', 'EGP', 'ERN', 'ETB', 'EUR', 'FJD', 'FKP', 'GBP', 'GEL', 'GGP', 'GHS', 'GIP', 'GMD', 'GNF', 'GTQ', 'GYD', 'HKD', 'HNL', 'HRK', 'HTG', 'HUF', 'IDR', 'ILS', 'IMP', 'INR', 'IQD', 'IRR', 'ISK', 'JEP', 'JMD', 'JOD', 'JPY', 'KES', 'KGS', 'KHR', 'KMF', 'KPW', 'KRW', 'KWD', 'KYD', 'KZT', 'LAK', 'LBP', 'LKR', 'LRD', 'LSL', 'LYD', 'MAD', 'MDL', 'MGA', 'MKD', 'MMK', 'MNT', 'MOP', 'MRO', 'MRU', 'MUR', 'MVR', 'MWK', 'MXN', 'MYR', 'MZN', 'NAD', 'NGN', 'NIO', 'NOK', 'NPR', 'NZD', 'OMR', 'PAB', 'PEN', 'PGK', 'PHP', 'PKR', 'PLN', 'PYG', 'QAR', 'RON', 'RSD', 'RUB', 'RWF', 'SAR', 'SBD', 'SCR', 'SDG', 'SEK', 'SGD', 'SHP', 'SLL', 'SOS', 'SRD', 'SSP', 'STD', 'STN', 'SVC', 'SYP', 'SZL', 'THB', 'TJS', 'TMT', 'TND', 'TOP', 'TRY', 'TTD', 'TWD', 'TZS', 'UAH', 'UGX', 'USD', 'UYU', 'UZS', 'VEF', 'VES', 'VND', 'VUV', 'WST', 'XAF', 'XAG', 'XAU', 'XCD', 'XDR', 'XOF', 'XPD', 'XPF', 'XPT', 'YER', 'ZAR', 'ZMW', 'ZWL'}

    is_forex = base in forex_currencies and quote in forex_currencies

    if is_forex:
      symbol = f"{base}{quote}=X"
      display_name = f"{base}/{quote}"
    else:
      symbol = base
      display_name = base

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=1y&interval=1d"
    try:
      req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
      data = urllib.request.urlopen(req, timeout=5).read()
      d_json = json.loads(data.decode('utf-8'))
      
      result = d_json.get('chart', {}).get('result')
      if not result:
        self.parent.send_msg(channel, f"Could not find data for ${display_name}")
        return

      timestamps = result[0].get('timestamp', [])
      indicators = result[0].get('indicators', {}).get('quote', [{}])[0]
      closes = indicators.get('close', [])
      valid_ts_closes = [(t, c) for (t, c) in zip(timestamps, closes) if c is not None and t is not None]
      meta = result[0].get('meta', {})
      t, price =  valid_ts_closes[-1] if valid_ts_closes else (None, None)
      t_last, price_last = valid_ts_closes[-2] if len(valid_ts_closes) > 1 else (None, None)
      # price = closes[-1]  # meta.get('regularMarketPrice')
      # prev_close = meta.get('chartPreviousClose')
      currency = meta.get('currency', '')

      if price is None:
        self.parent.send_msg(channel, f"Could not find price for ${display_name}")
        return


      def get_closest_price(target_ts):
        if not valid_ts_closes:
          return None
        best_c = None
        best_diff = float('inf')
        for t, c in valid_ts_closes[:-1]:
          diff = abs(t - target_ts)
          if diff < best_diff:
            best_diff = diff
            best_c = c
        return best_c

      current_ts = timestamps[-1] if timestamps else time.time()
      price_1d = get_closest_price(current_ts -   1 * 86400)
      price_1w = get_closest_price(current_ts -   7 * 86400)
      price_1m = get_closest_price(current_ts -  30 * 86400)
      price_1y = get_closest_price(current_ts - 365 * 86400)
      valid_closes = [c for c in closes if c is not None]
      price_ath = max(valid_closes) if valid_closes else None

      changes = []
      if price_1d is not None and price_1d > 0:
        changes.append(self.format_change(price, price_1d, '1d'))
      elif price_last is not None and price_last > 0:  # Only show last if no 1d
        t_delta_s = t - t_last
        t_delta_d = t_delta_s//86400
        changes.append(self.format_change(price, price_last, f'{t_delta_d}d'))
      if price_1w is not None and price_1w > 0:
        changes.append(self.format_change(price, price_1w, '1w'))
      if price_1m is not None and price_1m > 0:
        changes.append(self.format_change(price, price_1m, '1m'))
      if price_1y is not None and price_1y > 0:
        changes.append(self.format_change(price, price_1y, '1y'))
      if price_ath is not None and price_ath > 0:
        changes.append(self.format_change(price, price_ath, '1yH'))
        
      change_str = " | " + " ".join(changes) if changes else ""
        
      curr_suffix = f" {currency}" if currency else ""
      if price > 10:
        price_formatted = f"{price:.2f}{curr_suffix}"
      else:
        price_formatted = f"{price:.4g}{curr_suffix}"

      msg_numbers = f'{price_formatted}{change_str}'
      msg = f'{display_name}: {msg_numbers}'
      if not is_forex:
        msg_candidates = [  # in descending length
          f'[{meta["fullExchangeName"]}] {meta["longName"]} ({display_name}): {msg_numbers}',
          f'[{meta["fullExchangeName"]}] {meta["longName"]}: {msg_numbers}',
          f'[{meta["fullExchangeName"]}] {meta["shortName"]}: {msg_numbers}',
          f'[{meta["fullExchangeName"]}] {display_name}: {msg_numbers}',
          f'{display_name}: {msg_numbers}',
        ]
        for m in msg_candidates:
          msg = m
          if len(m) <= max_len:
            break  # Default to last one even if it's too long
      self.parent.send_msg(channel, msg)
    except urllib.error.HTTPError as e:
      if e.code == 404:
        self.parent.send_msg(channel, f"Could not find symbol ${display_name}")
      else:
        logging.error(f"Finance API HTTP error for query ${query}: {e}")
        self.parent.send_msg(channel, f"Error fetching data for ${query}.")
    except Exception as e:
      logging.error(f"Finance API error for query ${query}: {e}")
      self.parent.send_msg(channel, f"Error fetching data for ${query}.")

  def get_price_v2(self, channel, coin, currency='USD'):
    # Only uses Coinbase API, supports all Coinbase coins
    def get_cb_price_num(url):  # Will raise exceptions
      data = urllib.request.urlopen(url, timeout=5).read()
      d_json = json.loads(data.decode('utf-8'))
      return float(d_json['data']['amount'])

    coinbase_api_buy = f'https://api.coinbase.com/v2/prices/{coin}-{currency}/buy'
    coinbase_api_sell = f'https://api.coinbase.com/v2/prices/{coin}-{currency}/sell'
    coinbase_api_spot = f'https://api.coinbase.com/v2/prices/{coin}-{currency}/spot'
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
      coinbase_str = f'{coin}/{currency} - {coinbase}: Bid=${coinbase_bid:.2f} Ask=${coinbase_ask:.2f}'
    except BaseException as e:
      logging.debug(f'BTCv2: CoinBase buy/sell request/parse error - {e}')

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
      history_str = f'Spot=${coinbase_spot:.2f} {d_change} {w_change} {m_change} {y_change}'
    except BaseException as e:
      logging.debug(f'BTCv2: CoinBase history request/parse error - {e}')

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

    coinbase_api_buy = f'https://api.coinbase.com/v2/prices/BTC-{currency}/buy'
    coinbase_api_sell = f'https://api.coinbase.com/v2/prices/BTC-{currency}/sell'

    coindesk_str = None
    coinbase_str = None
    coindesk = 'CoinDesk'
    coinbase = 'Coinbase'

    if currency != 'USD':
      coindesk_str = f'{coindesk} does not support this currency.'
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

        coindesk_str = f'{coindesk}: Spot=${usd_price:.2f} {d_change} {w_change} {m_change}'
      except BaseException as e:
        logging.debug(f'BTC: CoinDesk request/parse error - {e}')

    try:
      coinbase_ask_data = urllib.request.urlopen(coinbase_api_buy).read()
      coinbase_bid_data = urllib.request.urlopen(coinbase_api_sell).read()
      coinbase_ask_json = json.loads(coinbase_ask_data.decode('utf-8'))
      coinbase_bid_json = json.loads(coinbase_bid_data.decode('utf-8'))
      coinbase_ask_price = float(coinbase_ask_json['data']['amount']) * self.scalefactor
      coinbase_bid_price = float(coinbase_bid_json['data']['amount']) * self.scalefactor
      coinbase_str = f'BTC/{currency} - {coinbase}: Bid=${coinbase_bid_price:.2f} Ask=${coinbase_ask_price:.2f}'
    except BaseException as e:
      logging.debug(f'BTC: CoinBase request/parse error - {e}')

    response_strs = [coinbase_str, coindesk_str]
    response_str = ' | '.join([s for s in response_strs if s is not None])
    self.parent.send_msg(msg_data['channel'], response_str)

  def format_change(self, new_price, old_price, char):
    change = (new_price-old_price)/old_price
    if change == 0:
      color = '\x035,99'
      return f'{color}{char}:=='
    elif change > 0:
      arrow = '↑'
      color = '\x033,99'
    else:
      arrow = '↓'
      color = '\x034,99'
    mag = abs(change)
    if mag > 0.5:
      change_str = f'{mag:.0%}'
    else:
      change_str = f'{mag*100:.3g}%'
    return f'{color}{char}:{arrow}{change_str}'
