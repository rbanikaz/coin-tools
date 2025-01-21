import argparse
import traceback
import random
from decimal import Decimal
from solders.pubkey import Pubkey as PublicKey  # type: ignore

from coin_tools.encryption import decrypt_data

from coin_tools.db import get_wallet_by_id, update_wallet_access_time, get_wallets_by_ids
from coin_tools.pump_fun.buy import buy as pumpfun_buy
from coin_tools.pump_fun.sell import sell as pumpfun_sell
from coin_tools.utils import randomize_by_percentage, random_delay_from_range, parse_ranges

from coin_tools.pump_fun.coin_data import fetch_coin_data
from coin_tools.solana.utils import (
  APPROX_RENT,
  get_solana_client,
  parse_private_key_bytes,
  fetch_sol_balance,
  fetch_token_balance
)


def get_data(args: argparse.Namespace):
    client = get_solana_client()
    mint_pubkey = PublicKey.from_string(args.ca)
    coin_data = fetch_coin_data(client, mint_pubkey)

    if coin_data.complete:
        print("Warning: This token has bonded and no longer tradeable on pump.fun")
        print()
        
    print("Token Info:")
    print(f"   Mint: {mint_pubkey}")
    print(f"   Name: {coin_data.metadata['name']} ({coin_data.metadata['symbol']})")
    if coin_data.price is None:
        print("   Price: NaN")
        print("   Market Cap: Unknown")
    else:
        print(f"   Price: {coin_data.price:.20f} SOL")
        print(f"   Market Cap: {(coin_data.market_cap):.4f} SOL")
    print(f"   Decimals: {coin_data.metadata['decimals']}")
    print(f"   Virtual Token Reserves: {coin_data.virtual_token_reserves}")
    print(f"   Virtual Sol Reserves: {coin_data.virtual_sol_reserves}")
    print(f"   Token Total Supply: {coin_data.token_total_supply}")
    print(f"   Complete: {coin_data.complete}")


def buy(args: argparse.Namespace):
    wallet = get_wallet_by_id(args.id)
    if not wallet:
        print(f"No wallet found with ID={args.id}")
        return
    try:
      mint_pubkey = PublicKey.from_string(args.ca)
      from_private_key = decrypt_data(wallet["private_key_encrypted"])
      buyer_keypair = parse_private_key_bytes(from_private_key)
    except Exception as e:
        print(f"Error parsing keypair: {e}")
        return
    
    client = get_solana_client()
    
    try:
      txn_signature = pumpfun_buy(client, 
                                  buyer_keypair, 
                                  mint_pubkey, 
                                  args.amount_in_sol, 
                                  args.slippage, 
                                  args.unit_limit, 
                                  args.unit_price, 
                                  args.confirm,
                                  args.jito_tip)
      print(f"Transaction Sent: {args.amount_in_sol} SOL to buy {args.ca}. Signature: {txn_signature}")
      update_wallet_access_time(args.id)
    except Exception as e:
      print(f"Error buying token: {e}")
      traceback.print_exc()
      return
    

def sell(args: argparse.Namespace):
    wallet = get_wallet_by_id(args.id)

    if not wallet:
        print(f"No wallet found with ID={args.id}")
        return
    
    try:
      mint_pubkey = PublicKey.from_string(args.ca)
      from_private_key = decrypt_data(wallet["private_key_encrypted"])
      seller_keypair = parse_private_key_bytes(from_private_key)
    except Exception as e:
        print(f"Error parsing keypair: {e}")
        return
    
    client = get_solana_client()
    
    try:
      txn_signature = pumpfun_sell(client, 
                                   seller_keypair, 
                                   mint_pubkey, 
                                   args.amount_in_token, 
                                   args.slippage, 
                                   args.unit_limit, 
                                   args.unit_price, 
                                   args.confirm,
                                   args.jito_tip)
      print(f"Transaction Sent: {args.amount_in_token} of {args.ca} sold. Signature: {txn_signature}")
      update_wallet_access_time(args.id)
    except Exception as e:
      print(f"Error selling token: {e}")
      traceback.print_exc()
      return


def bulk_buy(args: argparse.Namespace):
    buyer_wallets = get_wallets_by_ids(parse_ranges(args.ids))
    
    if not all(buyer_wallets):
      print("Error: Wallet(s) not found.")
      return
    
    if args.shuffle:
       random.shuffle(buyer_wallets)

    original_amount_in_sol = args.amount_in_sol

    for wallet in buyer_wallets:
      amount_in_sol = original_amount_in_sol

      if args.randomize:
          amount_in_sol = randomize_by_percentage(amount_in_sol, args.randomize)
      
      args.id = wallet['id']
      args.amount_in_sol = amount_in_sol
      print(f"Buying {amount_in_sol} {args.ca} for wallet ID {wallet['id']} {wallet['public_key']}...")
      buy(args)
      print()

      if args.random_delays:
          random_delay_from_range(args.random_delays)


def bulk_sell(args: argparse.Namespace):
    seller_wallets = get_wallets_by_ids(parse_ranges(args.ids))
    
    if not all(seller_wallets):
      print("Error: Wallet(s) not found.")
      return
    
    if args.shuffle:
       random.shuffle(seller_wallets)

    original_amount_in_token = args.amount_in_token

    for wallet in seller_wallets:
      amount_in_token = original_amount_in_token

      if args.randomize:
          amount_in_token = randomize_by_percentage(amount_in_token, args.randomize)
      
      args.id = wallet['id']
      args.amount_in_token = amount_in_token
      print(f"Selling {amount_in_token} tokens of {args.ca} for wallet ID {wallet['id']} {wallet['public_key']}...")
      sell(args)
      print()

      if args.random_delays:
          random_delay_from_range(args.random_delays)


def bulk_trade(args: argparse.Namespace):
    trader_wallets = get_wallets_by_ids(parse_ranges(args.ids))

    if not all(trader_wallets):
      print("Error: Wallet(s) not found.")
      return

    if args.shuffle:
      random.shuffle(trader_wallets)
               
    client = get_solana_client()
    mint_pubkey = PublicKey.from_string(args.ca)
    coin_data = fetch_coin_data(client, mint_pubkey)
    
    if coin_data is None or coin_data.complete:
        print("Error: This token has bonded and no longer tradeable on pump.fun")
        return
    
    token_price = coin_data.price

    original_amount_in_sol = args.amount_in_sol

    num_buy = 0
    num_sell = 0
    num_skip = 0

    for wallet in trader_wallets:
      amount_in_sol = original_amount_in_sol
      wallet_pubkey = PublicKey.from_string(wallet['public_key'])
      sol_balance = fetch_sol_balance(client, wallet_pubkey)
      token_balance = fetch_token_balance(client, wallet_pubkey, mint_pubkey)

      if args.randomize:
          amount_in_sol = randomize_by_percentage(amount_in_sol, args.randomize)
      
      args.id = wallet['id']
      args.amount_in_sol = amount_in_sol
      args.amount_in_token = float(Decimal(amount_in_sol) / token_price)
      print(f"Trading {amount_in_sol} SOL [{args.amount_in_token} tokens] for wallet ID {wallet['id']} {wallet['public_key']}...")

      prefer_buy = random.random() < args.buy_rate

      can_buy = sol_balance >= (args.amount_in_sol + APPROX_RENT)
      can_sell = token_balance and token_balance >= args.amount_in_token

      trade_action = None

      if prefer_buy:
          if can_buy:
            trade_action = 'buy'
            print(f"Wallet {wallet['id']} {wallet['public_key']} SOL balance {sol_balance} >= {args.amount_in_sol} buying.")
          elif can_sell:
            trade_action = 'sell'
            print(f"Wallet {wallet['id']} {wallet['public_key']} SOL balance {sol_balance} < {args.amount_in_sol} unable to buy, switching to sell.")
          else:          
            print(f"Wallet {wallet['id']} {wallet['public_key']} SOL balance {sol_balance} < {args.amount_in_sol} and token balance {token_balance} < {args.amount_in_token} unable to buy or sell.")
            trade_action = None
      else:
          if can_sell:
            trade_action = 'sell'
            print(f"Wallet {wallet['id']} {wallet['public_key']} token balance {token_balance} >= {args.amount_in_token} selling.")
          elif can_buy:
            trade_action = 'buy'
            print(f"Wallet {wallet['id']} {wallet['public_key']} token balance {token_balance} < {args.amount_in_token} unable to sell, switching to buy.")
          else:
            print(f"Wallet {wallet['id']} {wallet['public_key']} token balance {token_balance} < {args.amount_in_token} and SOL balance {sol_balance} < {args.amount_in_sol} unable to buy or sell.")
            trade_action = None

      if trade_action == 'buy':
        num_buy += 1
        buy(args)
      elif trade_action == 'sell':
        num_sell += 1
        sell(args)
      else:
        num_skip += 1

      print()
      if args.random_delays and trade_action:
        random_delay_from_range(args.random_delays)

      

    print(f"Buy: {num_buy}, Sell: {num_sell}, Total: {num_buy + num_sell + num_skip}, Skipped: {num_skip}")


def pumpfun_command(args: argparse.Namespace):
    if args.pump_fun_cmd == "get-data":
        get_data(args)
    elif args.pump_fun_cmd == "buy":
        buy(args)
    elif args.pump_fun_cmd == "bulk-buy":
        bulk_buy(args)
    elif args.pump_fun_cmd == "sell":
        sell(args)
    elif args.pump_fun_cmd == "bulk-sell":
        bulk_sell(args)
    elif args.pump_fun_cmd == "bulk-trade":
        bulk_trade(args)
    else:
        print("Unknown sub-command for pump-fun")
        if hasattr(args, 'parser'):
            args.parser.print_help()


def register(subparsers):
    manager_parser = subparsers.add_parser(
        "pump-fun",
        help="Buying and Selling on pump.fun."
    )
    manager_parser.set_defaults(func=pumpfun_command)

    pumpfun_subparsers = manager_parser.add_subparsers(dest="pump_fun_cmd")
    
    # get data
    get_data_subparser = pumpfun_subparsers.add_parser("get-data", help="Get coin data from pump.fun")
    get_data_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")

    # buy
    buy_subparser = pumpfun_subparsers.add_parser("buy", help="Buy coin from pump.fun")
    buy_subparser.add_argument("--id", type=int, required=True, help="Wallet ID.")
    buy_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    buy_subparser.add_argument("--amount-in-sol", type=float, required=True, help="Amount of SOL to spend")
    buy_subparser.add_argument("--slippage", type=int, default=5, help="Slippage tolerance percentage")
    buy_subparser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    buy_subparser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")
    buy_subparser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    buy_subparser.add_argument("--jito-tip", type=float, default = 30_000, help="JITO MEV Tip.")


    # bulk buy
    bulk_buy_subparser = pumpfun_subparsers.add_parser("bulk-buy", help="Bulk buy coin from pump.fun")
    bulk_buy_subparser.add_argument("--ids", required=True, help="Comma separated list of wallet ID's.")
    bulk_buy_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    bulk_buy_subparser.add_argument("--amount-in-sol", type=float, required=True, help="Amount of SOL to spend")
    bulk_buy_subparser.add_argument("--randomize", type=float, required=False, 
                                            help="Randomize by this percentage.  For example if amount is 100 and randomize is 0.1 then values will range from 90 to 110.")
    bulk_buy_subparser.add_argument("--random-delays", required=False, help="Insert random delays within this range in seconds (e.g. 1-20).")
    bulk_buy_subparser.add_argument("--slippage", type=int, default=5, help="Slippage tolerance percentage")
    bulk_buy_subparser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    bulk_buy_subparser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")
    bulk_buy_subparser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    bulk_buy_subparser.add_argument("--shuffle", action="store_true", help="Shuffle wallets before processing.")
    bulk_buy_subparser.add_argument("--jito-tip", type=float, default = 30_000, help="JITO MEV Tip.")
    
    # sell
    sell_subparser = pumpfun_subparsers.add_parser("sell", help="Sell coin on pump.fun")
    sell_subparser.add_argument("--id", type=int, required=True, help="Wallet ID.")
    sell_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    sell_subparser.add_argument("--amount-in-token", type=float, required=True, help="Amount of token to sell")
    sell_subparser.add_argument("--slippage", type=int, default=5, help="Slippage tolerance percentage")
    sell_subparser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    sell_subparser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")
    sell_subparser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    sell_subparser.add_argument("--jito-tip", type=float, default = 30_000, help="JITO MEV Tip.")

    # bulk sell
    bulk_sell_subparser = pumpfun_subparsers.add_parser("bulk-sell", help="Bulk sell coin on pump.fun")
    bulk_sell_subparser.add_argument("--ids", required=True, help="Comma separated list of wallet ID's.")
    bulk_sell_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    bulk_sell_subparser.add_argument("--amount-in-token", type=float, required=True, help="Amount of token to sell")
    bulk_sell_subparser.add_argument("--randomize", type=float, required=False, 
                                            help="Randomize by this percentage.  For example if amount is 100 and randomize is 0.1 then values will range from 90 to 110.")
    bulk_sell_subparser.add_argument("--random-delays", required=False, help="Insert random delays within this range in seconds (e.g. 1-20).")
    bulk_sell_subparser.add_argument("--slippage", type=int, default=5, help="Slippage tolerance percentage")
    bulk_sell_subparser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    bulk_sell_subparser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")
    bulk_sell_subparser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    bulk_sell_subparser.add_argument("--shuffle", action="store_true", help="Shuffle wallets before processing.")
    bulk_sell_subparser.add_argument("--jito-tip", type=float, default = 30_000, help="JITO MEV Tip.")

    # bulk trade
    bulk_trade_subparser = pumpfun_subparsers.add_parser("bulk-trade", help="Bulk trade on pump.fun.  Attempt to buy and sell within a distribution.")
    bulk_trade_subparser.add_argument("--ids", required=True, help="Comma separated list of wallet ID's.")
    bulk_trade_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    bulk_trade_subparser.add_argument("--amount-in-sol", type=float, required=True, help="Keep transaction centered around this amount of SOL.")
    bulk_trade_subparser.add_argument("--randomize", type=float, required=False, 
                                            help="Randomize by this percentage.  For example if amount is 100 and randomize is 0.1 then values will range from 90 to 110.")
    bulk_trade_subparser.add_argument("--random-delays", required=False, help="Insert random delays within this range in seconds (e.g. 1-20).")
    bulk_trade_subparser.add_argument("--buy-rate", type=float, default=.5, help="On average will attempt to buy at this rate across the wallets.  Depending on the wallet balance, the actual rate may vary." +
                                     "For example, if all the wallets have tokens but not enough SOL, they will all try to sell.")
    bulk_trade_subparser.add_argument("--slippage", type=int, default=5, help="Slippage tolerance percentage")
    bulk_trade_subparser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    bulk_trade_subparser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")
    bulk_trade_subparser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    bulk_trade_subparser.add_argument("--shuffle", action="store_true", help="Shuffle wallets before processing.")
    bulk_trade_subparser.add_argument("--jito-tip", type=float, default = 30_000, help="JITO MEV Tip.")

