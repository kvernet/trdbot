#!/usr/bin/env python3

import sys
from pathlib import Path
sys.path.append(str(Path.cwd()))
from tabulate import tabulate

from trading.cb import CbTrading

cb = CbTrading()
cb.loadApi("api/cdp_api_key.json")

product_id = "BTC-USDC"
ref_price  = None
cb.initialize(product_id, ref_price)

cb.setTradeCondition(trade_price_var=[-0.0001, 0.0003], loss_stopped=True)
cb.setStopLoss(-0.0002)

execute      = None
update_price = False
cb.run(execute, update_price)
