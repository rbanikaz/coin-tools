
import os
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solana.rpc.api import Client

from spl.token.instructions import (
    TransferParams as SplTransferParams,
    get_associated_token_address,
)

from decimal import Decimal

APPROX_RENT = 0.002

def get_solana_client() -> Client:
    """Returns a Solana RPC client."""
    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")
    return Client(rpc_url)

def parse_private_key_bytes(secret_bytes:bytes) -> Keypair:
    """Handles parsing a private key from bytes."""
    #    If the user has a 64-byte expanded key, use Keypair.from_bytes().
    #    If it's a 32-byte seed, use Keypair.from_seed().
    #    Below, we'll try from_bytes first; if that fails or if it's 32 bytes, use from_seed.
    if len(secret_bytes) == 64:
        return Keypair.from_bytes(secret_bytes)
    elif len(secret_bytes) == 32:
        return Keypair.from_seed(secret_bytes)
    else:
        raise Exception(f"Private key must be 32 or 64 bytes, but got length {len(secret_bytes)}.")

def fetch_sol_balance(client: Client, pubkey: PublicKey) -> Decimal:
    resp = client.get_balance(pubkey)
    lamports = resp.value
    return Decimal(lamports) / Decimal(1_000_000_000)

def fetch_token_balance(client: Client, wallet_pubkey: PublicKey, mint_pubkey: PublicKey) -> Decimal:
    """Derives the token account and fetches the balance."""
    ata = get_associated_token_address(owner=wallet_pubkey, mint=mint_pubkey)
    resp = client.get_token_account_balance(ata)

    try:
        balance_info = resp.value
    except AttributeError:
        return None

    if balance_info is None:
        return 0

    raw_amount_str = str(balance_info.amount)
    decimals = balance_info.decimals
    token_balance = Decimal(raw_amount_str) / (Decimal(10) ** Decimal(decimals))
    return token_balance


