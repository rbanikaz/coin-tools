import argparse
import base58
from solders.keypair import Keypair

from coin_tools.encryption import encrypt_data, decrypt_data
from coin_tools.solana_utils import parse_private_key_bytes
from coin_tools.db import (
    insert_wallet,
    get_wallet_by_id,
    get_all_wallets,
    update_wallet_access_time
)

def create_wallet(args: argparse.Namespace):
    if not args.name:  
        print("Error: must specify --name for the wallet.")
        return
    
    name = args.name
    keypair = Keypair()
    public_key_str = str(keypair.pubkey())
    secret_bytes = keypair.secret()
    encrypted_key = encrypt_data(secret_bytes)
    insert_wallet(name, public_key_str, encrypted_key)

    print("Wallet created!")
    print(f"Public Key: {public_key_str}")


def list_wallets(args: argparse.Namespace):
    wallets = get_all_wallets()
    if not wallets:
        print("No wallets found.")
        return

    for w in wallets:
        print(f"ID: {w['id']}, Name: {w['name']}, Public Key: {w['public_key']}, "
              f"Status: {w['status']}, Last Accessed: {w['last_accessed_timestamp']}")


def get_wallet(args: argparse.Namespace):
    if not args.id:
        print("Error: must specify --id <wallet_id> for get.")
        return

    wallet = get_wallet_by_id(args.id)
    if not wallet:
        print(f"No wallet found with ID {args.id}")
        return

    # Update the 'last_accessed_timestamp'
    update_wallet_access_time(args.id)

    print("Wallet info:")
    print(f"  ID: {wallet['id']}")
    print(f"  Name: {wallet['name']}")
    print(f"  Public Key: {wallet['public_key']}")
    print(f"  Status: {wallet['status']}")
    print(f"  Last Accessed: {wallet['last_accessed_timestamp']}")

    if args.decrypt:
        decrypted = decrypt_data(wallet['private_key_encrypted'])
        # Convert bytes -> base58
        private_key_b58 = base58.b58encode(decrypted).decode('utf-8')
        print(f"  Private Key (base58): {private_key_b58}")


def import_wallet(args: argparse.Namespace):
    """
    Imports a wallet from just a base58-encoded private key.
    We derive the public key automatically from the private key.
    """
    if not args.private_key:
        print("Error: must specify --private-key in base58 format.")
        return

    if not args.name:  
        print("Error: must specify --name for the wallet.")
        return

    name = args.name
    kp = None
    # 1) Decode base58 -> raw bytes
    try:
        secret_bytes = base58.b58decode(args.private_key)
    # 2) Create the Keypair
        kp = parse_private_key_bytes(secret_bytes)
    except Exception as e:
        print(f"Error decoding private key from base58: {e}")
        return

    # 3) Get the public key
    public_key_str = str(kp.pubkey())

    # 4) Encrypt the secret key
    encrypted_key = encrypt_data(secret_bytes)

    # 5) Insert into DB
    insert_wallet(name, public_key_str, encrypted_key)

    print("Wallet imported successfully.")
    print(f"Public Key: {public_key_str}")


def wallets_command(args: argparse.Namespace):
    if args.wallet_cmd == "create":
        create_wallet(args)
    elif args.wallet_cmd == "list":
        list_wallets(args)
    elif args.wallet_cmd == "get":
        get_wallet(args)
    elif args.wallet_cmd == "import":
        import_wallet(args)
    else:
        print("Unknown sub-command for wallets")
        if hasattr(args, 'parser'):
            args.parser.print_help()


def register(subparsers):
    manager_parser = subparsers.add_parser(
        "wallets",
        help="Manage wallets (create, list, get, import)."
    )
    manager_parser.set_defaults(func=wallets_command)

    wallet_subparsers = manager_parser.add_subparsers(dest="wallet_cmd")

    # create
    create_parser = wallet_subparsers.add_parser("create", help="Create a new Solana wallet.")
    create_parser.add_argument("--name", required=True, help="Name of the wallet")

    # list
    list_parser = wallet_subparsers.add_parser("list", help="List all wallets.")

    # get
    get_parser = wallet_subparsers.add_parser("get", help="Get a single wallet by ID.")
    get_parser.add_argument("--id", type=int, required=True, help="Wallet ID")
    get_parser.add_argument("--decrypt", action="store_true", help="Print the private key in plaintext/base58")

    # import
    import_parser = wallet_subparsers.add_parser("import", help="Import an existing wallet from private key only.")
    import_parser.add_argument("--name", required=True, help="Name of the wallet")
    import_parser.add_argument("--private-key", required=True, help="Base58-encoded private key.")
