from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.message import Message
from solana.rpc.api import Client
from solana.rpc.types import TxOpts

from solana.rpc.types import TokenAccountOpts
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token._layouts import ACCOUNT_LAYOUT, MINT_LAYOUT
from spl.token.instructions import (
    TransferParams as SplTransferParams,
    get_associated_token_address,
    create_idempotent_associated_token_account,
)
from spl.token.constants import TOKEN_PROGRAM_ID

from decimal import Decimal
from base64 import b64decode
import json
from coin_tools.db import get_token_metadata, upsert_token_metadata
from coin_tools.solana.metaplex_parse import parse_metaplex

TOKEN_METADATA_PROGRAM_ID = PublicKey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
UNKNOWN_TOKEN = {"name": "Unknown", "symbol": "???", "uri": ""} 

known_tokens = get_token_metadata()

def fetch_token_metadata(client: Client, mint_pubkey: PublicKey) -> dict:
    """
    Returns Token metadata such as name and ticker for a given CA using the program derived address and metaplex standard layout.
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
    mint_str = str(mint_pubkey)
    
    resp = client.get_account_info(mint_pubkey)
    if resp.value is None:
        # Possibly not a valid mint or no data
        raise RuntimeError(f"No mint account found: {mint_pubkey}")

    data_b64 = resp.value.data
    decoded_mint = MINT_LAYOUT.parse(data_b64)
    return decoded_mint.decimals