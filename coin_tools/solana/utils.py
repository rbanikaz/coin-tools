
import os
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
from coin_tools.solana.tokens import fetch_token_metadata

APPROX_RENT = 0.002

def get_solana_client() -> Client:
    rpc_url = os.getenv("COINTOOLS_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("COINTOOLS_RPC_URL environment variable is not set.")
    return Client(rpc_url)

def parse_private_key_bytes(secret_bytes:bytes) -> Keypair:
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
    # Derive associated token account
    ata = get_associated_token_address(owner=wallet_pubkey, mint=mint_pubkey)
    resp = client.get_token_account_balance(ata)

    try:
        balance_info = resp.value
    except AttributeError:
        print(f"Error fetching token balance for ATA={ata}: {resp}")
        return

    if balance_info is None:
        print(f"No token account found for CA={args.ca} or zero balance.")
        return

    raw_amount_str = str(balance_info.amount)
    decimals = balance_info.decimals
    token_balance = Decimal(raw_amount_str) / (Decimal(10) ** Decimal(decimals))
    return token_balance


def fetch_token_accounts(client: Client, wallet_pubkey: PublicKey):
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

def get_or_create_token_account(client: Client, payer_pubkey: PublicKey, owner_pubkey: PublicKey, mint_pubkey: PublicKey, signer_keypair: Keypair) -> PublicKey:
    ata = get_associated_token_address(owner=owner_pubkey, mint=mint_pubkey)
     
    response = client.get_account_info(ata)
        
    if not response.value:
        sol_balance = fetch_sol_balance(client, payer_pubkey)
   
        if sol_balance < APPROX_RENT:
            raise Exception(f"Recipient Account does not exist and payer does not have enough SOL to create it.")
        
        print(f"Token Account {ata} does not exist. Creating...")
        create_ata_ix = create_idempotent_associated_token_account(
            payer=payer_pubkey,
            owner=owner_pubkey,
            mint=mint_pubkey
        )

        blockhash_resp = client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        message = Message.new_with_blockhash(
            instructions=[create_ata_ix],
            blockhash=recent_blockhash,
            payer=payer_pubkey,
        )

        transaction = Transaction.new_unsigned(message)
        transaction.sign([signer_keypair], recent_blockhash=recent_blockhash)

        response = client.send_transaction(transaction, opts=TxOpts(skip_confirmation=False))
        if response.value:
            print(f"Transaction confirmed. Signature: {response.value}")
        else:
            raise Exception(f"Failed to send transaction: {response}")
    

    return ata