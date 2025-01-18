#!/usr/bin/env python3

import argparse
from coin_tools.db import init_db
from coin_tools.commands.wallets import register as register_wallets
from coin_tools.commands.balances import register as register_balances
from coin_tools.commands.transfers import register as register_transfers
from coin_tools.commands.pump_fun import register as register_pumpfun


def main():
    parser = argparse.ArgumentParser(
        prog="coin-tools",
        description="Tools for working on the Solana blockchain."
    )

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Initialize DB
    init_db()

    # Register sub-commands
    register_wallets(subparsers)
    register_balances(subparsers)
    register_transfers(subparsers)
    register_pumpfun(subparsers)

    args = parser.parse_args()

    # If no command is specified, print help
    if not args.command:
        parser.print_help()
    else:
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()

if __name__ == "__main__":
    print()
    main()
    print()
