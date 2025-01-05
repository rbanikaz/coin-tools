import argparse
import os, traceback
from decimal import Decimal
from solders.transaction import Transaction
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.message import Message
from solders.transaction import VersionedTransaction

from solders.rpc.responses import SendTransactionResp
from solders.instruction import CompiledInstruction
from solders.hash import Hash

from solana.rpc.api import Client
from solana.rpc.types import TxOpts

from spl.token.instructions import (
    transfer as spl_transfer,
    TransferParams as SplTransferParams,
    get_associated_token_address,
    create_associated_token_account,
)
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID

from coin_tools.solana_utils import APPROX_RENT
from coin_tools.solana_utils import parse_private_key_bytes, get_mint_decimals, get_token_accounts, fetch_sol_balance
from coin_tools.db import get_wallet_by_id
from coin_tools.encryption import decrypt_data


def transfer_sol(args: argparse.Namespace):
    if not args.from_id or not args.to_id or not args.amount:
        print("Error: must specify --from-id, --to-id, and --amount.")
        return

    from_wallet = get_wallet_by_id(args.from_id)
    to_wallet = get_wallet_by_id(args.to_id)

    if not from_wallet or not to_wallet:
        print(f"Error: Wallet(s) not found.")
        return

    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")

    client = Client(rpc_url)

    try:
        from_pubkey = PublicKey.from_string(from_wallet["public_key"])
        to_pubkey = PublicKey.from_string(to_wallet["public_key"])
        amount_lamports = int(Decimal(args.amount) * 1_000_000_000)
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

    # send the transaction
    try:
      # Create the transfer instruction
      transfer_ix = transfer(
          TransferParams(
              from_pubkey=from_pubkey,
              to_pubkey=to_pubkey,
              lamports=amount_lamports
          )
      )

      # Get recent blockhash
      recent_blockhash = client.get_latest_blockhash().value.blockhash

      # Create transaction message
      message = Message.new_with_blockhash(
          instructions=[transfer_ix],
          blockhash=recent_blockhash,
          payer=from_pubkey
      )

      # Create and sign the transaction
      transaction = Transaction.new_unsigned(message)
      transaction.sign([from_keypair], recent_blockhash=recent_blockhash)

      # Send the transaction
      response = client.send_transaction(transaction)
      
      # Check response
      if response.value:
          print(f"Successfully transferred {args.amount} SOL from {from_wallet['public_key']} to {to_wallet['public_key']}.")
          print(f"Transaction sent successfully. Signature: {response.value}")
      else:
          print(f"Failed to send transaction: {response}")
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
        print(f"Error: Wallet(s) not found.")
        return

    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")

    client = Client(rpc_url)

    try:
        from_pubkey = PublicKey.from_string(from_wallet["public_key"])
        to_pubkey = PublicKey.from_string(to_wallet["public_key"])
        token_mint_pubkey = PublicKey.from_string(args.ca)
        amount = int(Decimal(args.amount) * (10 ** get_mint_decimals(client, token_mint_pubkey)))  # Adjust for token decimals
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

    # Get associated token accounts
    from_ata = get_associated_token_address(owner=from_pubkey, mint=token_mint_pubkey)
    to_ata = get_associated_token_address(owner=to_pubkey, mint=token_mint_pubkey)
    print(f"Sending From: WalletID: {args.from_id}, PublicKey: {from_wallet['public_key']} ATA: {from_ata}")
    print(f"Sending To: WalletID: {args.to_id}, PublicKey: {to_wallet['public_key']} ATA: {to_ata}")

    sol_balance = fetch_sol_balance(client, from_pubkey)
    instructions = []

    try:
        response = client.get_account_info(to_ata)
        
        if not response.value:
            if sol_balance < APPROX_RENT:
                print(f"Recipient Account does not exist and sender does not have enough SOL to create it.")
                return
            
            print(f"Creating associated token account for recipient: WalletID: {args.to_id}, PublicKey: {to_wallet['public_key']} ATA: {to_ata}")
            create_ata_ix = create_associated_token_account(
                payer=from_pubkey,
                owner=to_pubkey,
                mint=token_mint_pubkey
            )
            instructions.append(create_ata_ix)
    except Exception as e:
        print(f"Error checking/creating recipient ATA: {e}")
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
        instructions.append(transfer_ix)

        # Get recent blockhash
        recent_blockhash = client.get_latest_blockhash().value.blockhash

        # Create transaction message
        message = Message.new_with_blockhash(
            instructions=instructions,
            blockhash=recent_blockhash,
            payer=from_pubkey
        )

        # Create and sign the transaction
        transaction = Transaction.new_unsigned(message)
        transaction.sign([from_keypair], recent_blockhash=recent_blockhash)

        # Send the transaction
        response = client.send_transaction(transaction)
        
        # Check response
        if response.value:
            print(f"Successfully transferred {args.amount} tokens from {from_wallet['public_key']} to {to_wallet['public_key']}.")
            print(f"Transaction Signature: {response.value}")
        else:
            print(f"Failed to send transaction: {response}")
    except Exception as e:
        print(f"Error transferring token: {e}")
        traceback.print_exc()


def migrate(args: argparse.Namespace):
    if not args.from_id or not args.to_id:
        print("Error: must specify --from-id and --to-id.")
        return

    from_wallet = get_wallet_by_id(args.from_id)
    to_wallet = get_wallet_by_id(args.to_id)

    if not from_wallet or not to_wallet:
        print(f"Error: Wallet(s) not found.")
        return

    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")

    client = Client(rpc_url)
    from_pubkey = PublicKey.from_string(from_wallet["public_key"])
    to_pubkey = PublicKey.from_string(to_wallet["public_key"])

    if args.tokens:
      # Transfer all tokens
      token_accounts = get_token_accounts(client, from_pubkey)
      for entry in token_accounts:
          try:
              token_ca = entry["mint_pubkey"]
              real_balance = entry["real_balance"]
              if real_balance > 0:
                  args.ca = str(token_ca)
                  args.amount = str(real_balance)
                  transfer_token(args)
          except Exception as e:
              print(f"Error transferring token {entry['token_name']}: {e}")
              traceback.print_exc()
              return
          
    if args.sol:
      try:
          sol_balance = fetch_sol_balance(client, from_pubkey)
          amount_to_transfer = Decimal(sol_balance) - Decimal(0.002)  # Leave a little for fees
          args.amount = str(amount_to_transfer)
          transfer_sol(args)
      except Exception as e:
          print(f"Error transferring SOL during migration: {e}")


def transfers_command(args: argparse.Namespace):
    """
    Main dispatcher for 'transfers' subcommands.
    """
    if args.transfers_cmd == "transfer-sol":
        transfer_sol(args)
    elif args.transfers_cmd == "transfer-token":
        transfer_token(args)
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

    # transfer-token
    transfer_token_parser = transfers_subparsers.add_parser(
        "transfer-token",
        help="Transfer a token from one wallet to another."
    )
    transfer_token_parser.add_argument("--from-id", type=int, required=True, help="Source wallet ID.")
    transfer_token_parser.add_argument("--to-id", type=int, required=True, help="Destination wallet ID.")
    transfer_token_parser.add_argument("--amount", required=True, help="Amount of token to transfer.")
    transfer_token_parser.add_argument("--ca", required=True, help="Token contract/mint address (CA).")

    # migrate
    migrate_parser = transfers_subparsers.add_parser(
        "migrate",
        help="Migrate all SOL and tokens from one wallet to another."
    )
    migrate_parser.add_argument("--from-id", type=int, required=True, help="Source wallet ID.")
    migrate_parser.add_argument("--to-id", type=int, required=True, help="Destination wallet ID.")
    migrate_parser.add_argument("--tokens", action="store_true", help="Migrate tokens.")
    migrate_parser.add_argument("--sol", action="store_true", help="Migrate SOL.")
