import argparse
import base58
import base64

from solders.pubkey import Pubkey as PublicKey
from solana.rpc.api import Client

from spl.token.instructions import get_associated_token_address

from decimal import Decimal

import os
from coin_tools.encryption import decrypt_data
from coin_tools.db import (
    get_wallet_by_id,
    get_all_wallets,
)

from coin_tools.solana_utils import KNOWN_TOKENS, get_token_accounts, fetch_sol_balance


def get_sol_balance(args: argparse.Namespace):
    if not args.id:
        print("Error: must specify --id <wallet_id> for get-sol-balance.")
        return

    wallet = get_wallet_by_id(args.id)
    if not wallet:
        print(f"No wallet found with ID={args.id}")
        return

    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")

    try:
        pubkey = PublicKey.from_string(wallet["public_key"])
    except ValueError as e:
        print(f"Error parsing public key: {e}")
        return

    client = Client(rpc_url)

    sol_balance = fetch_sol_balance(client, pubkey)
    print(f"SOL balance for wallet ID={args.id} (pubkey={wallet['public_key']}): {sol_balance} SOL")


def get_token_balance(args):
    if not args.id or not args.ca:
        print("Error: must specify --id and --ca.")
        return

    wallet = get_wallet_by_id(args.id)
    if not wallet:
        print(f"No wallet found with ID={args.id}")
        return

    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")

    client = Client(rpc_url)

    try:
        wallet_pubkey = PublicKey.from_string(wallet["public_key"])
        token_mint_pubkey = PublicKey.from_string(args.ca)
    except ValueError as e:
        print(f"Error parsing pubkeys: {e}")
        return

    # Derive associated token account
    ata = get_associated_token_address(owner=wallet_pubkey, mint=token_mint_pubkey)
    print(f"ATA: {ata}")
    resp = client.get_token_account_balance(ata)

    # If it's an "InvalidParamsMessage" or other error, .value won't exist
    try:
        balance_info = resp.value
    except AttributeError:
        print(f"Error fetching token balance for ATA={ata}: {resp}")
        return

    # If the ATA doesn't exist or is 0, balance_info might be None
    if balance_info is None:
        print(f"No token account found for CA={args.ca} or zero balance.")
        return

    # Parse decimals/amount
    raw_amount_str = str(balance_info.amount)
    decimals = balance_info.decimals
    token_balance = Decimal(raw_amount_str) / (Decimal(10) ** Decimal(decimals))

    print(f"Token balance for wallet ID={args.id} (pubkey={wallet['public_key']}): {token_balance}")


def get_tokens(args):
    if not args.id:
        print("Error: must specify --id <wallet_id> for get-tokens.")
        return

    wallet = get_wallet_by_id(args.id)
    if not wallet:
        print(f"No wallet found with ID={args.id}")
        return

    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")

    try:
        wallet_pubkey = PublicKey.from_string(wallet["public_key"])
    except ValueError as e:
        print(f"Error parsing wallet public key: {e}")
        return


    client = Client(rpc_url) 
    
    token_accounts = get_token_accounts(client, wallet_pubkey)
    if len(token_accounts) ==  0:
        print("No token accounts found.")
        return

    print(f"Tokens for wallet {args.id} (pubkey={wallet['public_key']}):\n")
    for entry in token_accounts:
        print(f"({entry['token_name']}/{entry['token_ticker']}) CA: {entry['mint_pubkey']}")
        print(f"Balance: {entry['real_balance']}\n")


def get_total_balance(args):
    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")

    client = Client(rpc_url)

    wallets = get_all_wallets()
    if len(wallets) == 0:
        print("No wallets found.")
        return

    total_sol = 0
    total_tokens = {}

    for wallet in wallets:
        wallet_pubkey = PublicKey.from_string(wallet["public_key"])

        # 1) Fetch SOL balance
        resp = client.get_balance(wallet_pubkey)
        lamports = resp.value
        sol_balance = lamports / 1_000_000_000
        total_sol += sol_balance

        if args.list:
            print(f"Wallet ID={wallet['id']} ({wallet['name']}) Public Key={wallet['public_key']}")
            print(f"   SOL balance: {sol_balance} SOL")
            
        # 2) Fetch token accounts
        token_accounts = get_token_accounts(client, wallet_pubkey)
        for entry in token_accounts:
            mint_pubkey = entry["mint_pubkey"]
            real_balance = entry["real_balance"]

            if args.list:
                print(f"   {entry['token_name']} ({entry['token_ticker']}) CA: {mint_pubkey}")
                print(f"   Balance: {real_balance}\n")

            if mint_pubkey not in total_tokens:
                total_tokens[mint_pubkey] = 0

            total_tokens[mint_pubkey] += real_balance

        if args.list:
            print("\n")

    print(f"Total SOL balance: {total_sol} SOL")
    print("Total token balances:")
    for mint_pubkey, balance in total_tokens.items():
        token_name, token_ticker = KNOWN_TOKENS.get(
            str(mint_pubkey), ("Unknown", "???")
        )
        print(f"   {token_name} ({token_ticker}) CA: {mint_pubkey}")
        print(f"   Balance: {balance}\n")


def balances_command(args: argparse.Namespace):
    """
    Main dispatcher for 'balances' subcommands.
    """
    if args.balances_cmd == "get-sol-balance":
        get_sol_balance(args)
    elif args.balances_cmd == "get-token-balance":
        get_token_balance(args)
    elif args.balances_cmd == "get-tokens":
        get_tokens(args)
    elif args.balances_cmd == "get-total-balance":
        get_total_balance(args)
    else:
        print("Unknown sub-command for balances")
        if hasattr(args, 'parser'):
            args.parser.print_help()


def register(subparsers):
    """
    Registers the 'balances' command with all its sub-commands.
    """
    manager_parser = subparsers.add_parser(
        "balances",
        help="View SOL and SPL token balances."
    )
    manager_parser.set_defaults(func=balances_command)

    balances_subparsers = manager_parser.add_subparsers(dest="balances_cmd")

    # get-sol-balance
    get_sol_parser = balances_subparsers.add_parser(
        "get-sol-balance",
        help="Get the SOL balance for a wallet."
    )
    get_sol_parser.add_argument("--id", type=int, required=True, help="Wallet ID.")

    # get-token-balance
    get_token_parser = balances_subparsers.add_parser(
        "get-token-balance",
        help="Get the balance for a specific SPL token in a wallet."
    )
    get_token_parser.add_argument("--id", type=int, required=True, help="Wallet ID.")
    get_token_parser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")

    # get-tokens
    get_tokens_parser = balances_subparsers.add_parser(
        "get-tokens",
        help="List all tokens in a wallet with balances."
    )
    get_tokens_parser.add_argument("--id", type=int, required=True, help="Wallet ID.")

    # get-total-balance
    get_total_parser = balances_subparsers.add_parser(
        "get-total-balance",
        help="Get the total balance for all wallets."
    )
    get_total_parser.add_argument("--list", action="store_true", help="Lists the balances of all the wallets when calculating the total balance.")

