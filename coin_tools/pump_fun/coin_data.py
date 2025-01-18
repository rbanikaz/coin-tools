from dataclasses import dataclass
from typing import Optional
from construct import Flag, Int64ul, Padding, Struct
from solana.rpc.api import Client
from solders.pubkey import Pubkey as PublicKey  # type: ignore
from spl.token.instructions import get_associated_token_address
from coin_tools.pump_fun.constants import PUMP_FUN_PROGRAM

@dataclass
class CoinData:
    mint: PublicKey
    bonding_curve: PublicKey
    associated_bonding_curve: PublicKey
    virtual_token_reserves: int
    virtual_sol_reserves: int
    token_total_supply: int
    complete: bool

def fetch_virtual_reserves(client: Client, bonding_curve: PublicKey):
    bonding_curve_struct = Struct(
        Padding(8),
        "virtualTokenReserves" / Int64ul,
        "virtualSolReserves" / Int64ul,
        "realTokenReserves" / Int64ul,
        "realSolReserves" / Int64ul,
        "tokenTotalSupply" / Int64ul,
        "complete" / Flag
    )
    
    try:
        account_info = client.get_account_info(bonding_curve)
        data = account_info.value.data
        parsed_data = bonding_curve_struct.parse(data)
        return parsed_data
    except Exception:
        return None

def derive_bonding_curve_accounts(mint_pubkey: PublicKey):
    try:
        bonding_curve, _ = PublicKey.find_program_address(
            ["bonding-curve".encode(), bytes(mint_pubkey)],
            PUMP_FUN_PROGRAM
        )
        associated_bonding_curve = get_associated_token_address(bonding_curve, mint_pubkey)
        return bonding_curve, associated_bonding_curve
    except Exception:
        return None, None

def fetch_coin_data(client: Client, mint_pubkey: PublicKey) -> Optional[CoinData]:
    bonding_curve, associated_bonding_curve = derive_bonding_curve_accounts(mint_pubkey)
    if bonding_curve is None or associated_bonding_curve is None:
        raise Exception("Error deriving bonding curve accounts")

    virtual_reserves = fetch_virtual_reserves(client, bonding_curve)
    if virtual_reserves is None:
        raise Exception("Error fetching virtual reserves")

    return CoinData(
          mint=mint_pubkey,
          bonding_curve=bonding_curve,
          associated_bonding_curve=associated_bonding_curve,
          virtual_token_reserves=int(virtual_reserves.virtualTokenReserves),
          virtual_sol_reserves=int(virtual_reserves.virtualSolReserves),
          token_total_supply=int(virtual_reserves.tokenTotalSupply),
          complete=bool(virtual_reserves.complete),
      )
  

def sol_for_tokens(sol_spent, sol_reserves, token_reserves):
    new_sol_reserves = sol_reserves + sol_spent
    new_token_reserves = (sol_reserves * token_reserves) / new_sol_reserves
    token_received = token_reserves - new_token_reserves
    return round(token_received)

def tokens_for_sol(tokens_to_sell, sol_reserves, token_reserves):
    new_token_reserves = token_reserves + tokens_to_sell
    new_sol_reserves = (sol_reserves * token_reserves) / new_token_reserves
    sol_received = sol_reserves - new_sol_reserves
    return sol_received
