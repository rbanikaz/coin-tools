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
    RENT,
)

from coin_tools.solana.utils import send_transaction

from coin_tools.solana.tokens import fetch_token_metadata, fetch_or_create_token_account
from solana.constants import SYSTEM_PROGRAM_ID, LAMPORTS_PER_SOL
from spl.token.constants import TOKEN_PROGRAM_ID

from coin_tools.pump_fun.coin_data import fetch_coin_data, sol_for_tokens


def buy(
    client: Client,
    buyer_keypair: Keypair,
    mint_pubkey: PublicKey,
    amount_in_sol: float,
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
    buyer_pubkey = buyer_keypair.pubkey()
    buyer_token_account, create_ata_ix = fetch_or_create_token_account(
        client, buyer_pubkey, buyer_pubkey, mint_pubkey, buyer_keypair
    )
    
    virtual_sol_reserves = coin_data.virtual_sol_reserves / LAMPORTS_PER_SOL
    virtual_token_reserves = coin_data.virtual_token_reserves / token_dec
    amount = sol_for_tokens(amount_in_sol, virtual_sol_reserves, virtual_token_reserves)
    amount = int(amount * token_dec)

    slippage_adjustment = 1 + (slippage / 100)
    max_sol_cost = int((amount_in_sol * slippage_adjustment) * LAMPORTS_PER_SOL)
    print(f"Amount: {amount}, Max Sol Cost: {max_sol_cost}")


    MINT = coin_data.mint
    BONDING_CURVE = coin_data.bonding_curve
    ASSOCIATED_BONDING_CURVE = coin_data.associated_bonding_curve
    BUYER = buyer_pubkey
    BUYER_TOKEN_ACCOUNT = buyer_token_account 

    print("Creating swap instructions...")
    keys = [
        AccountMeta(pubkey=GLOBAL, is_signer=False, is_writable=False),
        AccountMeta(pubkey=FEE_RECIPIENT, is_signer=False, is_writable=True),
        AccountMeta(pubkey=MINT, is_signer=False, is_writable=False),
        AccountMeta(pubkey=BONDING_CURVE, is_signer=False, is_writable=True),
        AccountMeta(pubkey=ASSOCIATED_BONDING_CURVE, is_signer=False, is_writable=True),
        AccountMeta(pubkey=BUYER_TOKEN_ACCOUNT, is_signer=False, is_writable=True),
        AccountMeta(pubkey=BUYER, is_signer=True, is_writable=True),
        AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=RENT, is_signer=False, is_writable=False),
        AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
        AccountMeta(pubkey=PUMP_FUN_PROGRAM, is_signer=False, is_writable=False),
    ]

    data = bytearray()
    data.extend(bytes.fromhex("66063d1201daebea"))
    data.extend(struct.pack("<Q", amount))
    data.extend(struct.pack("<Q", max_sol_cost))
    swap_ix = Instruction(PUMP_FUN_PROGRAM, bytes(data), keys)

    instructions = [
        set_compute_unit_limit(unit_limit),
        set_compute_unit_price(unit_price)
    ]
    
    if create_ata_ix:
        instructions.append(create_ata_ix)

    instructions.append(swap_ix)
    
    print("Sending transaction...")
    txn_signature = send_transaction(client, buyer_keypair, instructions, should_confirm=confirm)

    return txn_signature
