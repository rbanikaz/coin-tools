
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair

from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token._layouts import ACCOUNT_LAYOUT, MINT_LAYOUT
from spl.token.instructions import get_associated_token_address

from decimal import Decimal

APPROX_RENT = 0.002

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


KNOWN_TOKENS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USD Coin", "USDC"),
    "CQJjvLKLuHcJNsvJh7jJ6bK2RS8MH68cGTpf6DJjpump": ("Weedcoin", "CHRONIC"),
    "7bVE6BZ2y2rEAvxP4dZmrmA1gT6BPHz3imsR5U8upump": ("Kekcoin", "KEK"),
    "J5CpjMaYHYdZu2WBUPT79mALDJM14FKCiVVPwUDcpump": ("FAPCOIN", "FAPCOIN"),
    "4cRLrAdyr9wgSFoEyCHr6UTZxtgMtvmFumfqLszDpump": ("Buttplug", "BPC"),
    "6ZjmgrShWc8kMrWMy3tdgTrjx3v3qivWHjecuKH2pump": ("Saint Nikolass", "NIKO"),
    "FyKnmtStdToJaHubELurksJ1K47nmFjzDrpLThMeXHwR" : ("BABY PURPLE PEPE", "BABYPURPE"),
    "7EUGc2cr8yw3RH5CHSubjU3RQvR5nAA3UDeksrc3n3wf" : ("Farmer Shitoshi", "ShitFarmer"),
}

def fetch_sol_balance(client: Client, pubkey: PublicKey) -> Decimal:
    resp = client.get_balance(pubkey)
    lamports = resp.value
    return Decimal(lamports) / Decimal(1_000_000_000)

# Track which mint pubkeys we've already decoded to avoid repeated RPC calls
mint_decimals_cache = {}
def get_mint_decimals(client: Client, mint_pubkey: PublicKey) -> int:
    mint_str = str(mint_pubkey)
    if mint_str in mint_decimals_cache:
        return mint_decimals_cache[mint_str]
    
    resp = client.get_account_info(mint_pubkey)
    if resp.value is None:
        # Possibly not a valid mint or no data
        raise RuntimeError(f"No mint account found: {mint_pubkey}")

    data_b64 = resp.value.data
    decoded_mint = MINT_LAYOUT.parse(data_b64)
    mint_decimals_cache[mint_str] = decoded_mint.decimals
    return decoded_mint.decimals


def get_token_accounts(client: Client, wallet_pubkey: PublicKey):
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

        # 2) Get decimals from the mint account
        decimals = get_mint_decimals(client, mint_pubkey)

        # 3) Convert raw amount to real balance
        real_balance = Decimal(amount) / (Decimal(10) ** decimals)

        # 4) Optional: name/ticker
        token_name, token_ticker = KNOWN_TOKENS.get(
            str(mint_pubkey), ("Unknown", "???")
        )

        results.append({
            "mint_pubkey": mint_pubkey,
            "amount": amount,
            "decimals": decimals,
            "real_balance": real_balance,
            "token_name": token_name,
            "token_ticker": token_ticker,
        })
    
    return results