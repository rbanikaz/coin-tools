import struct

from solana.rpc.api import Client

from solders.instruction import AccountMeta  # type: ignore

from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey as PublicKey  # type: ignore
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore
from solders.instruction import Instruction  # type: ignore


# from config import client, payer_keypair, UNIT_BUDGET, UNIT_PRICE
from coin_tools.pump_fun.constants import (
    EVENT_AUTHORITY,
    FEE_RECIPIENT,
    GLOBAL,
    PUMP_FUN_PROGRAM,
)

from coin_tools.solana.utils import send_transaction

from coin_tools.solana.tokens import fetch_token_metadata, fetch_or_create_token_account
from solana.constants import SYSTEM_PROGRAM_ID, LAMPORTS_PER_SOL
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID

from coin_tools.pump_fun.coin_data import fetch_coin_data, tokens_for_sol


def sell(
    client: Client,
    seller_keypair: Keypair,
    mint_pubkey: PublicKey,
    amount_in_tokens: float,
    slippage: int = 5,
    unit_limit: int = 100_000,
    unit_price: int = 1_000_000,
    confirm: bool = False,
) -> str:
    coin_data = fetch_coin_data(client, mint_pubkey)

    if not coin_data:
        raise Exception("Failed to retrieve coin data.")

    if coin_data.complete:
        raise Exception(
            "Warning: This token has bonded and is only tradable on Raydium."
        )

    token_metadata = fetch_token_metadata(client, mint_pubkey)
    token_dec = 10 ** token_metadata["decimals"]
    seller_pubkey = seller_keypair.pubkey()
    seller_token_account = fetch_or_create_token_account(
        client, seller_pubkey, seller_pubkey, mint_pubkey, seller_keypair
    )
    
    virtual_sol_reserves = coin_data.virtual_sol_reserves / LAMPORTS_PER_SOL
    virtual_token_reserves = coin_data.virtual_token_reserves / token_dec
    amount_in_sol = tokens_for_sol(amount_in_tokens, virtual_sol_reserves, virtual_token_reserves)
    amount = int(amount_in_tokens * token_dec)

    slippage_adjustment = 1 - (slippage / 100)
    min_sol_output = int((amount_in_sol * slippage_adjustment) * LAMPORTS_PER_SOL)
    print(f"Amount: {amount}, Min Sol Out: {min_sol_output}")

    MINT = coin_data.mint
    BONDING_CURVE = coin_data.bonding_curve
    ASSOCIATED_BONDING_CURVE = coin_data.associated_bonding_curve
    SELLER = seller_pubkey
    SELLER_TOKEN_ACCOUNT = seller_token_account 

    print("Creating swap instructions...")
    keys = [
        AccountMeta(pubkey=GLOBAL, is_signer=False, is_writable=False),
        AccountMeta(pubkey=FEE_RECIPIENT, is_signer=False, is_writable=True),
        AccountMeta(pubkey=MINT, is_signer=False, is_writable=False),
        AccountMeta(pubkey=BONDING_CURVE, is_signer=False, is_writable=True),
        AccountMeta(pubkey=ASSOCIATED_BONDING_CURVE, is_signer=False, is_writable=True),
        AccountMeta(pubkey=SELLER_TOKEN_ACCOUNT, is_signer=False, is_writable=True),
        AccountMeta(pubkey=SELLER, is_signer=True, is_writable=True),
        AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=ASSOCIATED_TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
        AccountMeta(pubkey=PUMP_FUN_PROGRAM, is_signer=False, is_writable=False),
    ]

    data = bytearray()
    data.extend(bytes.fromhex("33e685a4017f83ad"))
    data.extend(struct.pack("<Q", amount))
    data.extend(struct.pack("<Q", min_sol_output))
    swap_instruction = Instruction(PUMP_FUN_PROGRAM, bytes(data), keys)

    instructions = [
        set_compute_unit_limit(unit_limit),
        set_compute_unit_price(unit_price),
        swap_instruction
    ]
    
    print("Sending transaction...")
    txn_signature = send_transaction(client, seller_keypair, instructions, should_confirm=confirm)

    return txn_signature
