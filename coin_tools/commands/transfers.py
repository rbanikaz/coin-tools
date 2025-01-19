import argparse
import traceback

from decimal import Decimal

from solders.pubkey import Pubkey as PublicKey  #type: ignore
from solders.system_program import TransferParams, transfer
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore

from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import TransferParams as SplTransferParams
from spl.token.instructions import get_associated_token_address
from spl.token.instructions import transfer as spl_transfer

from coin_tools.utils import randomize_by_percentage, random_delay_from_range
from coin_tools.db import get_wallet_by_id, update_wallet_access_time
from coin_tools.encryption import decrypt_data
from coin_tools.solana.tokens import (
    fetch_or_create_token_account,
    fetch_token_accounts,
    fetch_token_metadata,
)
from coin_tools.solana.utils import (
    APPROX_RENT,
    fetch_sol_balance,
    get_solana_client,
    parse_private_key_bytes,
    send_transaction
)


def transfer_sol(args: argparse.Namespace):
    if not args.from_id or not args.to_id or not args.amount:
        print("Error: must specify --from-id, --to-id, and --amount.")
        return

    from_wallet = get_wallet_by_id(args.from_id)
    to_wallet = get_wallet_by_id(args.to_id)

    if not from_wallet or not to_wallet:
        print("Error: Wallet(s) not found.")
        return

    client = get_solana_client()

    try:
        from_pubkey = PublicKey.from_string(from_wallet["public_key"])
        to_pubkey = PublicKey.from_string(to_wallet["public_key"])
        amount_lamports = int(args.amount * 1_000_000_000)
    except ValueError as e:
        print(f"Error parsing public keys or amount: {e}")
        return

    # Decrypt private key
    try:
        from_private_key = decrypt_data(from_wallet["private_key_encrypted"])
        from_keypair = parse_private_key_bytes(from_private_key)
    except Exception as e:
        print(f"Error decrypting private key: {e}")
        traceback.print_exc()
        return

    try:
      transfer_ix = transfer(
          TransferParams(
              from_pubkey=from_pubkey,
              to_pubkey=to_pubkey,
              lamports=amount_lamports
          )
      )

      instructions = [
          set_compute_unit_limit(args.unit_limit),
          set_compute_unit_price(args.unit_price),
          transfer_ix
      ]

      txn_signature = send_transaction(client, from_keypair, instructions, should_confirm=args.confirm)
      if txn_signature:
        print(f"Transaction Sent: {args.amount} SOL from {from_wallet['public_key']} to {to_wallet['public_key']}.")
        print(f"Signature: {txn_signature}")
        update_wallet_access_time(args.from_id)
        update_wallet_access_time(args.to_id)

    except Exception as e:
      print(f"Error sending transaction: {e}")
      traceback.print_exc()


def transfer_token(args: argparse.Namespace):
    if not args.from_id or not args.to_id or not args.amount or not args.ca:
        print("Error: must specify --from-id, --to-id, --amount, and --ca.")
        return

    from_wallet = get_wallet_by_id(args.from_id)
    to_wallet = get_wallet_by_id(args.to_id)

    if not from_wallet or not to_wallet:
        print("Error: Wallet(s) not found.")
        return

    client = get_solana_client()
    
    try:
        from_pubkey = PublicKey.from_string(from_wallet["public_key"])
        to_pubkey = PublicKey.from_string(to_wallet["public_key"])
        token_mint_pubkey = PublicKey.from_string(args.ca)
        metadata = fetch_token_metadata(client, token_mint_pubkey)
        amount = int(args.amount * 10 ** metadata["decimals"])
    except ValueError as e:
        print(f"Error parsing public keys or amount: {e}")
        return

    # Decrypt private key
    try:
        from_private_key = decrypt_data(from_wallet["private_key_encrypted"])
        from_keypair = parse_private_key_bytes(from_private_key)
    except Exception as e:
        print(f"Error decrypting private key: {e}")
        traceback.print_exc()
        return
    try:
      # Get associated token accounts
      from_ata = get_associated_token_address(owner=from_pubkey, mint=token_mint_pubkey)
      to_ata, create_ata_ix = fetch_or_create_token_account(client, from_pubkey, to_pubkey, token_mint_pubkey, from_keypair)
      print(f"Sending From: WalletID: {args.from_id}, PublicKey: {from_wallet['public_key']} ATA: {from_ata}")
      print(f"Sending To: WalletID: {args.to_id}, PublicKey: {to_wallet['public_key']} ATA: {to_ata}")
    except Exception as e:
        print(f"Error getting or creating token accounts: {e}")
        traceback.print_exc()
        return    

    try:
        # Create the transfer instruction
        transfer_ix = spl_transfer(
            SplTransferParams(
                source=from_ata,
                dest=to_ata,
                owner=from_pubkey,
                amount=amount,
                program_id=TOKEN_PROGRAM_ID
            )
        )

        instructions = [
          set_compute_unit_limit(args.unit_limit),
          set_compute_unit_price(args.unit_price)
        ]

        if create_ata_ix:
          instructions.append(create_ata_ix)
        
        instructions.append(transfer_ix)
        
        txn_signature = send_transaction(client, from_keypair, instructions, should_confirm=args.confirm)
        if txn_signature:
            print(f"Transaction Sent: {args.amount} ({args.ca}) tokens from {from_wallet['public_key']} to {to_wallet['public_key']}.")
            print(f"Transaction Signature: {txn_signature}")
            update_wallet_access_time(args.from_id)
            update_wallet_access_time(args.to_id)
        
            
    except Exception as e:
        print(f"Error transferring token: {e}")
        traceback.print_exc()


def bulk_transfer_sol(args: argparse.Namespace):
    from_wallet = get_wallet_by_id(args.from_id)
    to_wallets = [get_wallet_by_id(id) for id in args.to_ids.split(",")]
    
    if not from_wallet or not all(to_wallets):
        print("Error: Wallet(s) not found.")
        return
    
    original_amount = args.amount

    for to_id in args.to_ids.split(","):
        amount = original_amount

        if args.randomize:
            amount = randomize_by_percentage(amount, args.randomize)
        
        args.to_id = to_id
        args.amount = amount
        
        transfer_sol(args)

        if args.random_delays:
            random_delay_from_range(args.random_delays)


def bulk_transfer_token(args: argparse.Namespace):
    from_wallet = get_wallet_by_id(args.from_id)
    to_wallets = [get_wallet_by_id(id) for id in args.to_ids.split(",")]
    
    if not from_wallet or not all(to_wallets):
        print("Error: Wallet(s) not found.")
        return
    
    original_amount = args.amount

    for to_id in args.to_ids.split(","):
        amount = original_amount

        if args.randomize:
            amount = randomize_by_percentage(amount, args.randomize)
        
        args.to_id = to_id
        args.amount = amount
        
        transfer_token(args)

        if args.random_delays:
            random_delay_from_range(args.random_delays)


def migrate(args: argparse.Namespace):
    from_wallet = get_wallet_by_id(args.from_id)
    to_wallet = get_wallet_by_id(args.to_id)

    if not from_wallet or not to_wallet:
        print("Error: Wallet(s) not found.")
        return

    client = get_solana_client()
    from_pubkey = PublicKey.from_string(from_wallet["public_key"])

    if args.tokens:
      # Transfer all tokens
      token_accounts = fetch_token_accounts(client, from_pubkey)
      for entry in token_accounts:
          try:
              token_ca = entry["mint_pubkey"]
              real_balance = entry["real_balance"]
              if real_balance > 0:
                  args.ca = str(token_ca)
                  args.amount = str(real_balance)
                  args.confirm = False
                  transfer_token(args)
          except Exception as e:
              print(f"Error transferring token {entry['token_name']}: {e}")
              traceback.print_exc()
              return
          
    if args.sol:
      try:
          sol_balance = fetch_sol_balance(client, from_pubkey)
          amount_to_transfer = Decimal(sol_balance) - Decimal(APPROX_RENT)  # Leave a little for rent
          args.amount = str(amount_to_transfer)
          args.confirm = False
          transfer_sol(args)
      except Exception as e:
          print(f"Error transferring SOL during migration: {e}")
          return


def transfers_command(args: argparse.Namespace):
    """
    Main dispatcher for 'transfers' subcommands.
    """
    if args.transfers_cmd == "transfer-sol":
        transfer_sol(args)
    elif args.transfers_cmd == "bulk-transfer-sol":
        bulk_transfer_sol(args)
    elif args.transfers_cmd == "transfer-token":
        transfer_token(args)
    elif args.transfers_cmd == "bulk-transfer-token":
        bulk_transfer_token(args)
    elif args.transfers_cmd == "migrate":
        migrate(args)
    else:
        print("Unknown sub-command for transfers")
        if hasattr(args, 'parser'):
            args.parser.print_help()


def register(subparsers):
    """
    Registers the 'transfers' command with all its sub-commands.
    """
    manager_parser = subparsers.add_parser(
        "transfers",
        help="Transfer SOL or tokens between wallets."
    )
    manager_parser.set_defaults(func=transfers_command)

    transfers_subparsers = manager_parser.add_subparsers(dest="transfers_cmd")

    # transfer-sol
    transfer_sol_parser = transfers_subparsers.add_parser(
        "transfer-sol",
        help="Transfer SOL from one wallet to another."
    )
    transfer_sol_parser.add_argument("--from-id", type=int, required=True, help="Source wallet ID.")
    transfer_sol_parser.add_argument("--to-id", type=int, required=True, help="Destination wallet ID.")
    transfer_sol_parser.add_argument("--amount", required=True, help="Amount of SOL to transfer.")
    transfer_sol_parser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    transfer_sol_parser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    transfer_sol_parser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")

    # # bulk-transfer-sol
    bulk_transfer_sol_parser = transfers_subparsers.add_parser(
        "bulk-transfer-sol",
        help="Bulk transfer sol from one wallet to set of wallets."
    )
    bulk_transfer_sol_parser.add_argument("--from-id", type=int, required=True, help="Source wallet ID.")
    bulk_transfer_sol_parser.add_argument("--to-ids", required=True, help="Comma separated list of destination wallet ID's.")
    bulk_transfer_sol_parser.add_argument("--amount", type=float, required=True, help="Amount of SOL to transfer.")
    bulk_transfer_sol_parser.add_argument("--randomize", type=float, required=False, 
                                            help="Randomize by this percentage.  For example if amount is 100 and randomize is 0.1 then values will range from 90 to 110.")
    bulk_transfer_sol_parser.add_argument("--random-delays", required=False, help="Insert random delays within this range in seconds (e.g. 1-20).")
    bulk_transfer_sol_parser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    bulk_transfer_sol_parser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    bulk_transfer_sol_parser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")


    # transfer-token
    transfer_token_parser = transfers_subparsers.add_parser(
        "transfer-token",
        help="Transfer a token from one wallet to another."
    )
    transfer_token_parser.add_argument("--from-id", type=int, required=True, help="Source wallet ID.")
    transfer_token_parser.add_argument("--to-id", type=int, required=True, help="Destination wallet ID.")
    transfer_token_parser.add_argument("--amount", type=float, required=True, help="Amount of token to transfer.")
    transfer_token_parser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    transfer_token_parser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    transfer_token_parser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    transfer_token_parser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")
    
    # bulk-transfer-token
    bulk_transfer_token_parser = transfers_subparsers.add_parser(
        "bulk-transfer-token",
        help="Bulk transfer a token from one wallet to set of wallets."
    )
    bulk_transfer_token_parser.add_argument("--from-id", type=int, required=True, help="Source wallet ID.")
    bulk_transfer_token_parser.add_argument("--to-ids", required=True, help="Comma separated list of destination wallet ID's.")
    bulk_transfer_token_parser.add_argument("--amount", type=float, required=True, help="Amount of token to transfer.")
    bulk_transfer_token_parser.add_argument("--randomize", type=float, required=False, 
                                            help="Randomize by this percentage.  For example if amount is 100 and randomize is 0.1 then values will range from 90 to 110.")
    bulk_transfer_token_parser.add_argument("--random-delays", required=False, help="Insert random delays within this range in seconds (e.g. 1-20).")
    bulk_transfer_token_parser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")
    bulk_transfer_token_parser.add_argument("--confirm", action="store_true", help="Confirm Transactions.")
    bulk_transfer_token_parser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    bulk_transfer_token_parser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")

    # migrate
    migrate_parser = transfers_subparsers.add_parser(
        "migrate",
        help="Migrate all SOL and tokens from one wallet to another."
    )
    migrate_parser.add_argument("--from-id", type=int, required=True, help="Source wallet ID.")
    migrate_parser.add_argument("--to-id", type=int, required=True, help="Destination wallet ID.")
    migrate_parser.add_argument("--tokens", action="store_true", help="Migrate tokens.")
    migrate_parser.add_argument("--sol", action="store_true", help="Migrate SOL.")
    migrate_parser.add_argument("--unit-limit", type=int, default=100_000, help="Unit limit")
    migrate_parser.add_argument("--unit-price", type=int, default=1_000_000, help="Unit price")
