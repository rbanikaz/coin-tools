#!/bin/bash

CURRENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
COINTOOLS_HOME="$CURRENT_DIR/.."

if [ $# -lt 4 ]; then
    echo "Usage: $0 <wallet_prefix> <number_of_wallets> <seed_wallet_id> <sol_to_seed>"
    exit 1
fi

prefix=$1
num_wallets=$2
seed_wallet_id=$3
sol_to_seed=$4

wallet_list=""

for ((i = 1; i <= num_wallets; i++)); do
    
    wallet_id=$($COINTOOLS_HOME/coin-tools wallets create --name "$prefix$i" | grep "Wallet ID" | awk '{print $3}')
    
    echo "Wallet $prefix$i created with id $wallet_id"
    
    if [ -z "$wallet_list" ]; then
        wallet_list="$wallet_id"
    else
        wallet_list="$wallet_list,$wallet_id"
    fi
done

echo "$wallet_list"

echo "$COINTOOLS_HOME/coin-tools transfers bulk-transfer-sol --from-id $seed_wallet_id --to-ids $wallet_list --amount $sol_to_seed --randomize 0.1 --random-delays 1-10"
$COINTOOLS_HOME/coin-tools transfers bulk-transfer-sol --from-id $seed_wallet_id --to-ids $wallet_list --amount $sol_to_seed --randomize 0.1 --random-delays 1-10
