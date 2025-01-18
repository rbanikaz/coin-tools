
import os
from decimal import Decimal
from dis import Instruction

from solana.constants import LAMPORTS_PER_SOL
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.keypair import Keypair  #type: ignore
from solders.message import Message  #type: ignore
from solders.pubkey import Pubkey as PublicKey  #type: ignore  #type: ignore
from solders.transaction import Transaction  #type: ignore
from spl.token.instructions import (
    get_associated_token_address,
)


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
    return Decimal(lamports) / Decimal(LAMPORTS_PER_SOL)

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

def send_transaction(client:Client, keypair: Keypair, instructions:list[Instruction], should_confirm:bool=False):
    """Sends a transaction to the Solana network."""

    # Get recent blockhash
    recent_blockhash = client.get_latest_blockhash().value.blockhash

    # Create transaction message
    message = Message.new_with_blockhash(
        instructions=instructions,
        blockhash=recent_blockhash,
        payer=keypair.pubkey(),
    )

    # Create and sign the transaction
    transaction = Transaction.new_unsigned(message)
    transaction.sign([keypair], recent_blockhash=recent_blockhash)

    # Send the transaction
    txn_opts = TxOpts(skip_confirmation=False) if should_confirm else TxOpts(skip_confirmation=True)
    response = client.send_transaction(transaction, opts=txn_opts)
    
    # Check response
    if response.value:
        return response.value
    else:
        raise Exception(f"Failed to send transaction: {response}")
