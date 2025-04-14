#!/usr/bin/env python3

import sys
from pathlib import Path
sys.path.append(str(Path.cwd()))
from tabulate import tabulate

from trading.cb import CbTrading

cb = CbTrading()
cb.loadApi("api/cdp_api_key.json")

accounts = cb.getAccounts()['accounts']
wallets = []
for acc in accounts:
    wallets.append(
        [acc['name'], acc['available_balance']['value'], acc['active'], acc['ready']]
    )

print(tabulate(wallets, headers=["Name", "Balance", "Active", "Ready"], tablefmt="pretty"))
