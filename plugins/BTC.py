import settings
import datetime
import logging
import json
import urllib.request
import time

class BTC():
    #cooldown time for requests in sec
    cooldown = 60*10
    last_request = 0

    def BTC(self, main_ref, msg_info):
        if msg_info["channel"] == settings.NICK:
            return None

        if msg_info["message"].lower().startswith("!btc"):
            current_time = time.time()
            if current_time > self.last_request + self.cooldown:
                self.last_request = current_time
                price_str = self.get_price()
                main_ref.send_msg(msg_info["channel"], price_str)

    def get_price(self):
        current_api = "https://api.coindesk.com/v1/bpi/currentprice.json"
        lastM_api = "https://api.coindesk.com/v1/bpi/historical/close.json"
        try:
            current_r = urllib.request.urlopen(current_api).read()
            lastM_r = urllib.request.urlopen(lastM_api).read()
        except urllib.error.HTTPError:
            logging.debug("BTC: couldn't make the request")
            return ""
        try:
            current_j = json.loads(current_r.decode('utf-8'))
            lastM_j = json.loads(lastM_r.decode('utf-8'))
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
            eur_price = current_j["bpi"]["EUR"]["rate"]
        except:
            logging.debug("BTC: the api probably changed")
            return ""

        d_change = (1 - (float(usd_price.replace(",","")) / float(usd_price_1d))) * -100
        week_change = (1 - (float(usd_price.replace(",","")) / float(usd_price_1w))) * -100
        month_change = (1 - (float(usd_price.replace(",","")) / float(usd_price_1m))) * -100

        response_str = "฿: $" + usd_price.split(".", 1)[0] + "/€" + eur_price.split(".", 1)[0] +  " " + \
            self.format_change(d_change, "d") + " " + self.format_change(week_change, "w") + " " + self.format_change(month_change, "m")

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

#(((“Powered by CoinDesk”)))
