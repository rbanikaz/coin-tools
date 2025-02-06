#!/usr/bin/env python3
import datetime
import argparse
import sys
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
                                                
    # Initialize DB
    init_db()

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
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
    start = datetime.datetime.now()
    print()
    print("   ______      _     ______            __    ")
    print("  / ____/___  (_)___/_  __/___  ____  / /____")
    print(" / /   / __ \/ / __ \/ / / __ \/ __ \/ / ___/")
    print("/ /___/ /_/ / / / / / / / /_/ / /_/ / (__  ) ")
    print("\____/\____/_/_/ /_/_/  \____/\____/_/____/  ")
    print()
    print("Welcome to the Coin Tools CLI!")
    print("Current Time: ", start.strftime("%Y-%m-%d %H:%M:%S"))
    print("Command Line: ", " ".join(sys.argv[1:]))
    print()
    main()
    print()
    print("Time Taken: ", round((datetime.datetime.now() - start).total_seconds(), 1), "seconds")