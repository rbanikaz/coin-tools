import argparse

import base58
from solders.keypair import Keypair #type: ignore

from coin_tools.db import (
    get_all_wallets,
    get_token_metadata,
    get_wallet_by_id,
    insert_wallet,
    update_name,
    update_private_key,
    update_wallet_access_time,
    upsert_token_metadata,
    update_wallet_status
)
from coin_tools.encryption import decrypt_data, encrypt_data
from coin_tools.solana.utils import parse_private_key_bytes

def __create_wallet(name: str):
    keypair = Keypair()
    public_key_str = str(keypair.pubkey())
    secret_bytes = keypair.secret()
    encrypted_key = encrypt_data(secret_bytes)
    id = insert_wallet(name, public_key_str, encrypted_key)
    return id, public_key_str

def create_wallet(args: argparse.Namespace):
    name = args.name
    id, public_key_str = __create_wallet(name)

    print(f"Wallet ID {id} created!")
    print(f"Public Key: {public_key_str}")

def bulk_create_wallets(args: argparse.Namespace):
    count = args.count
    name_prefix = args.name_prefix

    ids_created = []

    for i in range(count):
        name = f"{name_prefix}{i}"
        id = __create_wallet(name)
        ids_created.append(id)
    
    print(f"{count} wallets created with prefix '{name_prefix}'.")
    print(f"IDs: {', '.join(str(i) for i in ids_created)}")

def list_wallets(args: argparse.Namespace):
    wallets = get_all_wallets()
    if not wallets:
        print("No wallets found.")
        return

    for w in wallets:
        print(f"ID: {w['id']}, Name: {w['name']}, Public Key: {w['public_key']}, "
              f"Status: {w['status']}, Last Accessed: {w['last_accessed_timestamp']}")


def get_wallet(args: argparse.Namespace):

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

def rename_wallet(args: argparse.Namespace):
    update_name(args.id, args.name)
    print(f"Wallet ID {args.id} renamed to '{args.name}'.")

def manage_metadata(args: argparse.Namespace):
    if args.list:
        metadata = get_token_metadata()
        if not metadata:
            print("No tickers found.")
            return
        for ca, metadata in metadata.items():
            print(f"{ca}: {metadata})")
        return
    elif args.update:
        if not args.ca or not args.name or not args.symbol or not args.uri or not args.decimals:
            print("Missing required arguments: --ca, --name, --symbol, --uri, --decimals")
            return
        upsert_token_metadata(args.ca, args.name, args.symbol, args.uri, int(args.decimals))
        print(f"Ticker for {args.ca} updated.")

def manage_encryption(args: argparse.Namespace):
    if args.generate_key:
        from cryptography.fernet import Fernet
        print("Generating a new encryption key...")
        print(Fernet.generate_key().decode())
        print("Please store this key securely.")
        print("You will need it to decrypt any data encrypted with this key.")
        print("You must set this key as the COINTOOLS_ENC_KEY environment variable.")
    elif args.rotate_key:
        all_wallets = get_all_wallets()
        num_wallets = len(all_wallets)
        print(f"There are {num_wallets} wallets stored in this database")
        print("Rotating the encryption key will re-encrypt all private keys.")
        print("Current private keys will not be able to be read until the new key is set as COINTOOLS_ENC_KEY.")
        print("Be sure to back up the database and the current encryption key.")
        
        new_key = input("Please enter a new encryption key and press Enter to continue: ")
        if not new_key:
            print("No key entered. Exiting.")
            return
        
        print("Rotating the encryption key...")
        for wallet in all_wallets:
            decrypted = decrypt_data(wallet['private_key_encrypted'])
            re_encrypted = encrypt_data(decrypted, override_key=new_key)
            update_private_key(wallet['id'], re_encrypted)
        print("Encryption key rotation complete.")
        print("Please set the new key as the COINTOOLS_ENC_KEY environment variable.")
    else:
        print("Unknown sub-command for encryption")
        if hasattr(args, 'parser'):
            args.parser.print_help()

def delete_wallet(args: argparse.Namespace):
    print("Delete wallet stub, just soft deletion, accounts still exist on blockchain.")
    update_wallet_status(args.id, "deleted")
    print(f"Wallet ID {args.id} deleted.")

def wallets_command(args: argparse.Namespace):
    if args.wallet_cmd == "create":
        create_wallet(args)
    elif args.wallet_cmd == "bulk-create":
        bulk_create_wallets(args)
    elif args.wallet_cmd == "list":
        list_wallets(args)
    elif args.wallet_cmd == "get":
        get_wallet(args)
    elif args.wallet_cmd == "import":
        import_wallet(args)
    elif args.wallet_cmd == "rename":
        rename_wallet(args)
    elif args.wallet_cmd == "metadata":
        manage_metadata(args)
    elif args.wallet_cmd == "encryption":
        manage_encryption(args)
    elif args.wallet_cmd == "delete":
        delete_wallet(args)
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

    # bulk-create
    bulk_create_parser = wallet_subparsers.add_parser("bulk-create", help="Bulk create wallets.")
    bulk_create_parser.add_argument("--count", type=int, required=True, help="Number of wallets to create.")
    bulk_create_parser.add_argument("--name-prefix", required=True, help="Prefix for wallet names.")

    # list
    wallet_subparsers.add_parser("list", help="List all wallets.") 

    # get
    get_parser = wallet_subparsers.add_parser("get", help="Get a single wallet by ID.")
    get_parser.add_argument("--id", type=int, required=True, help="Wallet ID")
    get_parser.add_argument("--decrypt", action="store_true", help="Print the private key in plaintext/base58")

    # import
    import_parser = wallet_subparsers.add_parser("import", help="Import an existing wallet from private key only.")
    import_parser.add_argument("--name", required=True, help="Name of the wallet")
    import_parser.add_argument("--private-key", required=True, help="Base58-encoded private key.")

    # rename
    rename_parser = wallet_subparsers.add_parser("rename", help="Rename a wallet.")
    rename_parser.add_argument("--id", type=int, required=True, help="Wallet ID")
    rename_parser.add_argument("--name", required=True, help="New name for the wallet")

    # metadata
    metadata_parser = wallet_subparsers.add_parser("metadata", help="Manage metadata for known tokens.")
    metadata_parser.add_argument("--list", required=False, action="store_true", help="List all known tokens.")
    metadata_parser.add_argument("--update", required=False, action="store_true", help="Update (or add if not exists) to known tokens.")
    metadata_parser.add_argument("--ca", required=False, help="Token contract/mint address (CA).")
    metadata_parser.add_argument("--name", required=False, help="Coin name.")
    metadata_parser.add_argument("--symbol", required=False, help="Coin ticker symbol.")
    metadata_parser.add_argument("--uri", required=False, help="Coin URI.")
    metadata_parser.add_argument("--decimals", required=False, help="Coin decimals.")

    # encryption
    encryption_parser = wallet_subparsers.add_parser("encryption", help="Manage encryption settings.")
    encryption_parser.add_argument("--generate-key", required=False, action="store_true", help="Generate a new encryption key.")
    encryption_parser.add_argument("--rotate-key", required=False, action="store_true", help="Rotate the encryption key.")

    # delete wallet
    delete_parser = wallet_subparsers.add_parser("delete", help="Delete a wallet (stub).")
    delete_parser.add_argument("--id", type=int, required=True, help="Wallet ID.")