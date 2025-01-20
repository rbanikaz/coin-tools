import argparse

from solana.constants import LAMPORTS_PER_SOL
from solders.pubkey import Pubkey as PublicKey #type: ignore

from coin_tools.utils import parse_ranges
from coin_tools.db import (
    get_all_wallets,
    get_wallet_by_id,
    get_wallets_by_ids,
    get_wallets_by_name_prefix,
)

from coin_tools.solana.tokens import fetch_token_accounts, fetch_token_metadata
from coin_tools.solana.utils import (
    fetch_sol_balance,
    fetch_token_balance,
    get_solana_client,
)

def get_sol_balance(args: argparse.Namespace):
    wallet = get_wallet_by_id(args.id)
    if not wallet:
        print(f"No wallet found with ID={args.id}")
        return

    try:
        pubkey = PublicKey.from_string(wallet["public_key"])
    except ValueError as e:
        print(f"Error parsing public key: {e}")
        return

    client = get_solana_client()

    sol_balance = fetch_sol_balance(client, pubkey)
    print(f"Wallet ID={args.id} ({wallet['name']}), PublicKey={wallet['public_key']}):\n")
    print(f"   SOL Balance: {sol_balance} SOL")


def get_token_balance(args):
    wallet = get_wallet_by_id(args.id)
    if not wallet:
        print(f"No wallet found with ID={args.id}")
        return

    client = get_solana_client()

    try:
        wallet_pubkey = PublicKey.from_string(wallet["public_key"])
        token_mint_pubkey = PublicKey.from_string(args.ca) if args.ca else None
    except ValueError as e:
        print(f"Error parsing pubkeys: {e}")
        return
    
    if args.ca is None:
        token_accounts = fetch_token_accounts(client, wallet_pubkey)
        if len(token_accounts) ==  0:
            print("No token accounts found.")
            return

        print(f"Wallet ID={args.id} ({wallet['name']}), Public Key={wallet['public_key']}):\n")
        for entry in token_accounts:
            print(f"   {entry['token_name']} ({entry['token_ticker']}) CA: {entry['mint_pubkey']}")
            print(f"   Balance: {entry['real_balance']}\n")
    else:
        token_balance = fetch_token_balance(client, wallet_pubkey, token_mint_pubkey)
        if token_balance is None:
            print(f"No token account found for {args.ca}")
            return
        
        metadata = fetch_token_metadata(client, token_mint_pubkey)
        token_name = metadata["name"]
        token_ticker = metadata["symbol"]
        print(f"Wallet ID={args.id} ({wallet['name']}), Public Key={wallet['public_key']}:\n")
        print(f"   {token_name} ({token_ticker}) CA: {token_mint_pubkey}")
        print(f"   Balance: {token_balance}\n")


def get_total_balance(args):
    client = get_solana_client()

    if not args.prefix and not args.ids:
        wallets = get_all_wallets()
    else:
        wallets = []
        if args.prefix:
            wallets += get_wallets_by_name_prefix(args.prefix)
        
        if args.ids:
            wallets += get_wallets_by_ids(parse_ranges(args.ids))

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
        sol_balance = lamports / LAMPORTS_PER_SOL
        total_sol += sol_balance

        if args.list:
            print(f"Wallet ID={wallet['id']} ({wallet['name']}), Public Key={wallet['public_key']}")
            print(f"   SOL Balance: {sol_balance} SOL")
            
        # 2) Fetch token accounts
        token_accounts = fetch_token_accounts(client, wallet_pubkey)
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

    print("Total Wallets:", len(wallets))
    print()
    print(f"Total SOL Balance: {total_sol} SOL")
    print()
    print("Total Token Balances:")
    for mint_pubkey, balance in total_tokens.items():
        if args.ca and str(mint_pubkey) != args.ca:
            continue
        metadata = fetch_token_metadata(client, mint_pubkey)
        token_name = metadata["name"]
        token_ticker = metadata["symbol"]
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
    get_token_parser.add_argument("--ca", required=False, help="Token contract/mint address (CA).")

    # get-total-balance
    get_total_parser = balances_subparsers.add_parser(
        "get-total-balance",
        help="Calculate the total balance for wallets."
    )
    get_total_parser.add_argument("--list", action="store_true", help="Lists the balances of all the wallets while calculating the total balance.")
    get_total_parser.add_argument("--prefix", required=False, help="Find wallets by name (case insensitive prefix).")
    get_total_parser.add_argument("--ids", required=False, help="Find wallets by ids (comma separated with ranges).")
    get_total_parser.add_argument("--ca", required=False, help="Token contract/mint address (CA).")

