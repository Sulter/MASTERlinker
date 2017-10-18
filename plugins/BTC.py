import settings
import logging
import json
import urllib
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
        api = "https://api.coindesk.com/v1/bpi/currentprice.json"
        try:
            r = urllib.request.urlopen(api).read()
        except urllib.error.HTTPError:
            logging.debug("couldn't make the request")
        try:
            cont = json.loads(r.decode('utf-8'))
        except:
            logging.debug("couldn't decode the request")
            

        try:
            usd_price = cont["bpi"]["USD"]["rate"].split(".", 1)[0]
            eur_price = cont["bpi"]["EUR"]["rate"].split(".", 1)[0]
        except:
            logging.debug("the api probably changed")

        response_str = "$" + usd_price + "/" + eur_price + "€"

        return response_str

#(((“Powered by CoinDesk”)))
