import argparse
import traceback

from solana.constants import LAMPORTS_PER_SOL
from solders.pubkey import Pubkey as PublicKey  # type: ignore

from coin_tools.encryption import decrypt_data

from coin_tools.db import get_wallet_by_id, update_wallet_access_time
from coin_tools.pump_fun.buy import buy as pumpfun_buy
from coin_tools.pump_fun.coin_data import fetch_coin_data
from coin_tools.solana.tokens import fetch_token_metadata
from coin_tools.solana.utils import (
  get_solana_client,
  parse_private_key_bytes,
)


def get_data(args: argparse.Namespace):
    client = get_solana_client()
    mint_pubkey = PublicKey.from_string(args.ca)
    token_metadata = fetch_token_metadata(client, mint_pubkey)

    try:
      coin_data = fetch_coin_data(client, mint_pubkey)
    except Exception as e:
        print(f"Error fetching coin data: {e}")
        return

    token_decimals = token_metadata["decimals"]
    
    virtual_sol_reserves = coin_data.virtual_sol_reserves / LAMPORTS_PER_SOL
    virtual_token_reserves = coin_data.virtual_token_reserves / 10**token_decimals
    total_supply = coin_data.token_total_supply / 10**token_decimals

    if virtual_token_reserves > 0:
      token_price = virtual_sol_reserves / virtual_token_reserves
    else:
      token_price = None

    if coin_data.complete:
        print("Warning: This token has bonded and no longer tradeable on pump.fun")
        print()
        
    print("Token Info:")
    print(f"   Mint: {mint_pubkey}")
    print(f"   Name: {token_metadata['name']} ({token_metadata['symbol']})")
    if token_price is None:
        print("   Price: NaN")
        print("   Market Cap: Unknown")
    else:
        print(f"   Price: {token_price:.20f} SOL")
        print(f"   Market Cap: {(token_price * total_supply):.4f} SOL")
    print(f"   Decimals: {token_decimals}")
    print(f"   Virtual Token Reserves: {virtual_token_reserves}")
    print(f"   Virtual Sol Reserves: {virtual_sol_reserves}")
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
      txn_signature = pumpfun_buy(client, buyer_keypair, mint_pubkey, args.amount_in_sol, args.slippage, args.unit_limit, args.unit_price)
      print(f"Transaction Sent: {args.amount_in_sol} SOL to buy {args.ca}. Signature: {txn_signature}")
      update_wallet_access_time(args.id)
    except Exception as e:
      print(f"Error buying token: {e}")
      traceback.print_exc()
      return

def pumpfun_command(args: argparse.Namespace):
    if args.pump_fun_cmd == "get-data":
        get_data(args)
    elif args.pump_fun_cmd == "buy":
        buy(args)
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
    
    get_data_subparser = pumpfun_subparsers.add_parser("get-data", help="Get coin data from pump.fun")
    get_data_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")

    buy_subparser = pumpfun_subparsers.add_parser("buy", help="Buy coin from pump.fun")
    buy_subparser.add_argument("--id", type=int, required=True, help="Wallet ID.")
    buy_subparser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    buy_subparser.add_argument("--amount-in-sol", type=float, required=True, help="Amount of SOL to spend")
    buy_subparser.add_argument("--slippage", type=int, default=5, help="Slippage tolerance percentage")
    buy_subparser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    buy_subparser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")

