import sys
import json
import requests
import uuid
import time
import logging
from json import dumps
from decimal import Decimal, ROUND_DOWN

from coinbase.rest import RESTClient
from requests.exceptions import HTTPError

class CbTrading():
    """Trading on Coinbase Cex."""    
    
    def __init__(self):
        """Constructor of the Tranding on Coinbase."""
        
        self.client = None
        self.product_id = None
        self.base_currency, self.quote_currency = None, None
        self.product = None        
        self.balance = [0., 0.]
        self.ref_price = None
        self.entry_price = None
        self.buy_when_price_var = -0.003
        self.sell_when_price_var = 0.006
        self.api_key_loaded = False
        self.initialized = False
        self.stop_loss = -0.02
        self.loss_stopped = False
        
        # Configure the logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("log.txt"),
                #logging.StreamHandler()  # This prints to console too
            ]
        )
    
    
    def loadApi(self, cdp_api_key_path):
        """Load the CDP API KEY and create a client."""
        
        try:
            with open(cdp_api_key_path, 'r') as f:
                data = json.load(f)
            api_key = data['name']
            api_secret = data['privateKey']            
            self.client = RESTClient(api_key=api_key, api_secret=api_secret)
            self.api_key_loaded = True        
        except FileNotFoundError:
            logging.info("File %s not found.", cdp_api_key_path)
        except json.JSONDecodeError:
            logging.info("Failed to decode JSON. The file might be malformed.")        
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
    
    
    def initialize(self, product_id, ref_price=None):
        """Initialize the trading state."""
        
        if not self.api_key_loaded:
            logging.info("The API key should be loaded first.")
            return
        
        try:
            self.product_id = product_id
            self.base_currency, self.quote_currency = self.product_id.split("-")
            self.product = self.safeGetProduct()
            self.setBalance()
            self.initialized = True
            if ref_price is None:
                self.ref_price = self.getPrice()
            else:
                self.ref_price = ref_price
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
    
    
    def info(self):
        """Print the info of the trading state."""
        
        try:
            print("------------------------------------")
            print(f"Pair      : {self.product_id}")
            print(f"Balance   : {self.balance}")
            print(f"Ref. price: {self.ref_price}")
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
    
    
    def getAccounts(self):
        """Get accounts details."""
        
        if not self.api_key_loaded:
            logging.info("The API key should be loaded first.")
            return
        
        try:
            return self.client.get_accounts()
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
    
    
    def safeGetProduct(self, retries=5, base_delay=1, max_delay=10):
        for attempt in range(retries):
            try:
                return self.client.get_product(self.product_id)
            
            except (HTTPError, ConnectionError, Timeout) as e:
                wait = min(base_delay * (2 ** attempt), max_delay)
                jitter = random.uniform(0, wait * 0.5)
                sleep_time = wait + jitter
                
                print(f"[Retry {attempt + 1}/{retries}] Error: {e}. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            
            except Exception as e:
                print(f"[Retry {attempt + 1}/{retries}] Unexpected error: {e}")
                time.sleep(2)
        
        print("[Warning] Failed to fetch product after retries. Using fallback value.")
        return self.entry_price
    
    
    def getPrice(self):
        """Get the actual price of the product"""
        
        product = self.safeGetProduct()
        return float(product["price"])
    
    
    def get_unique_order_id(self):
        return str(uuid.uuid4())
    
    
    def setStopLoss(self, stop_loss):
        self.stop_loss = stop_loss
    
    
    def setBalance(self):
        try:
            accounts = self.getAccounts()
            for acc in accounts['accounts']:
                data = acc.to_dict()
                if data['currency'] == self.quote_currency:
                    self.balance[0] = float(data['available_balance']['value'])
                if data['currency'] == self.base_currency:
                    self.balance[1] = float(data['available_balance']['value'])
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
    
    
    def format_size(self, value, precision="0.01"):
        """Format size"""
        
        return Decimal(value).quantize(Decimal(precision), rounding=ROUND_DOWN)
    
    
    def buy(self, balance, cur_price):
        """Execute buy order."""
        
        if balance[0] <= 1:
            return
        
        try:
            order = self.client.market_order_buy(
                client_order_id=self.get_unique_order_id(),
                product_id=self.product_id,
                quote_size=str(self.format_size(self.balance[0]))
            )            
            if order['success']:
                time.sleep(15)
                order_id = order['success_response']['order_id']
                fills = self.client.get_fills(order_id=order_id)
                self.info_logger.info(json.dumps(fills.to_dict(), indent=2))
                self.setBalance()
                self.entry_price = cur_price
                print(f"Buy order executed at price {cur_price}.")
                return True
            else:
                error_response = order['error_response']
                logging.info(error_response)
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
        
        return False
    
    
    def sell(self, balance, cur_price):
        """Execute sell order."""
        
        if balance[1] <= 0:
            return
        
        try:
            order = self.client.market_order_sell(
                client_order_id=self.get_unique_order_id(),
                product_id=self.product_id,
                base_size=str(self.format_size(self.balance[1], "0.00000001"))
            )            
            if order['success']:
                time.sleep(15)
                order_id = order['success_response']['order_id']
                fills = self.client.get_fills(order_id=order_id)
                self.info_logger.info(json.dumps(fills.to_dict(), indent=2))                
                self.setBalance()
                self.entry_price = None
                print(f"Sell order executed at price {cur_price}.")
                return True
            else:
                error_response = order['error_response']
                logging.info(error_response)
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
        
        return False
    
    
    def run(self, execute=None, update_price=False):
        """Run the auto trade."""
        
        if not self.initialized:
            logging.info("The bot should be initialized first.")
            return
        
        try:
            if execute is None:
                execute = self.execute
            
            while True:
                cur_price = self.getPrice()
                price_var = cur_price/self.ref_price - 1
                print(f"Ref price: {self.ref_price} & entry price: {self.entry_price} & current price: {cur_price} [{round(100*price_var, 5)}%]")
                
                if self.loss_stopped and self.entry_price is not None:
                    loss_var = cur_price/self.entry_price - 1
                    if loss_var <= self.stop_loss:
                        self.sell(self.balance, cur_price)
                        sys.exit(1)
                
                ok = execute(self.balance, self.ref_price, cur_price)
                if ok and update_price:
                    self.ref_price = cur_price
                
                self.info()
                print("------------------------------------------")
        except Exception as e:
            logging.info("An unexpected error occurred: %s", e)
    
    
    def setTradeCondition(self, trade_price_var=[-0.003, 0.006], loss_stopped=False):
        """Set trade price variation condition
        Default value: trade_price_var=[-0.003, 0.006]
        """
        
        self.buy_when_price_var  = trade_price_var[0]
        self.sell_when_price_var = trade_price_var[1]
        self.loss_stopped = loss_stopped
    
    
    def execute(self, balance, ref_price, cur_price):
        """Execute the trade under certain predefined condition 
        with the whole balance based on the price variation
        """
        
        price_var = cur_price/ref_price - 1
        # buy if price variation meets condition
        if price_var <= self.buy_when_price_var:
            return self.buy(balance, cur_price)
        
        # sell if price variation meets condition
        if price_var >= self.sell_when_price_var:
            return self.sell(balance, cur_price)
        
        return False
