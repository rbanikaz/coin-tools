from decimal import Decimal

from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts, TxOpts
from solders.keypair import Keypair #type: ignore
from solders.message import Message #type: ignore
from solders.pubkey import Pubkey as PublicKey #type: ignore
from solders.transaction import Transaction #type: ignore
from spl.token._layouts import ACCOUNT_LAYOUT, MINT_LAYOUT
from spl.token.constants import TOKEN_PROGRAM_ID

from spl.token.instructions import (
    create_idempotent_associated_token_account,
    get_associated_token_address,
)

from coin_tools.db import get_token_metadata, upsert_token_metadata
from coin_tools.solana.metaplex_parse import parse_metaplex
from coin_tools.solana.utils import APPROX_RENT, fetch_sol_balance

TOKEN_METADATA_PROGRAM_ID = PublicKey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
UNKNOWN_TOKEN = {"name": "Unknown", "symbol": "???", "uri": ""} 

known_tokens = get_token_metadata()

def fetch_token_metadata(client: Client, mint_pubkey: PublicKey) -> dict:
    """
    Fetches Token metadata such as name and ticker for a given CA using the program derived address and metaplex standard layout.
    """
    mint_str = str(mint_pubkey)
    
    if mint_str in known_tokens:
        return known_tokens[mint_str]
    
    #otherwise metadata needs to be fetched from PDA and mint address
    seeds = [
        b"metadata",
        bytes(TOKEN_METADATA_PROGRAM_ID),
        bytes(mint_pubkey),
    ]

    metadata_pubkey, _ = PublicKey.find_program_address(seeds, TOKEN_METADATA_PROGRAM_ID)
    resp = client.get_account_info(metadata_pubkey)

    account_info = resp.value
    metadata = UNKNOWN_TOKEN
    if account_info and account_info.data:
        raw_data = bytes(account_info.data)
        metadata = parse_metaplex(raw_data)
    
    decimals = fetch_mint_decimals(client, mint_pubkey)
    metadata["decimals"] = decimals
    upsert_token_metadata(mint_str, metadata["name"], metadata["symbol"], metadata["uri"], decimals)
    return metadata


def fetch_mint_decimals(client: Client, mint_pubkey: PublicKey) -> int:
    """Fetch the number of decimals for a given mint from blockchain."""
    resp = client.get_account_info(mint_pubkey)
    if resp.value is None:
        # Possibly not a valid mint or no data
        raise RuntimeError(f"No mint account found: {mint_pubkey}")

    data_b64 = resp.value.data
    decoded_mint = MINT_LAYOUT.parse(data_b64)
    return decoded_mint.decimals


def fetch_token_accounts(client: Client, wallet_pubkey: PublicKey):
    """
    Fetches all token accounts for a given wallet pubkey from the blockchain.
    """
    token_opts = TokenAccountOpts(
        program_id=TOKEN_PROGRAM_ID,
        encoding="base64",
    )
    resp = client.get_token_accounts_by_owner(
        owner=wallet_pubkey,
        opts=token_opts
    )

    results = []

    token_accounts = resp.value
    if not token_accounts:
        return results

    for entry in token_accounts:
        # 1) Decode the token account data
        data_b64 = entry.account.data

        acct = ACCOUNT_LAYOUT.parse(data_b64)
        mint_pubkey = PublicKey(acct.mint)
        amount = acct.amount

        # 2) Fetch the metadata from the mint account
        metadata = fetch_token_metadata(client, mint_pubkey)
        token_name = metadata["name"]
        token_ticker = metadata["symbol"]
        decimals = metadata["decimals"]
        # 3) Convert raw amount to real balance
        real_balance = Decimal(amount) / (Decimal(10) ** decimals)

        # 4) Append metadata
        results.append({
            "mint_pubkey": mint_pubkey,
            "amount": amount,
            "decimals": decimals,
            "real_balance": real_balance,
            "token_name": token_name,
            "token_ticker": token_ticker,
        })

    return results


def fetch_or_create_token_account(client: Client, payer_pubkey: PublicKey, owner_pubkey: PublicKey, mint_pubkey: PublicKey, signer_keypair: Keypair) -> PublicKey:
    """
    Fetches associated token account from the blockchain or creates it if it does not exist.
    """
    ata = get_associated_token_address(owner=owner_pubkey, mint=mint_pubkey)

    response = client.get_account_info(ata)

    if not response.value:
        sol_balance = fetch_sol_balance(client, payer_pubkey)

        if sol_balance < APPROX_RENT:
            raise Exception("Recipient Account does not exist and payer does not have enough SOL to create it.")

        print(f"Token Account {ata} does not exist. Creating...")
        create_ata_ix = create_idempotent_associated_token_account(
            payer=payer_pubkey,
            owner=owner_pubkey,
            mint=mint_pubkey
        )

        return ata, create_ata_ix

    return ata, None