```
   ______      _     ______            __    
  / ____/___  (_)___/_  __/___  ____  / /____
 / /   / __ \/ / __ \/ / / __ \/ __ \/ / ___/
/ /___/ /_/ / / / / / / / /_/ / /_/ / (__  ) 
\____/\____/_/_/ /_/_/  \____/\____/_/____/  
                                             
```

# CoinTools
CoinTools is a command line application for working with solana wallets.  

It stores wallets locally in sqlite and has scripts for getting balances, moving sol and tokens around and trading

### Donation address:
```
DYwtGzZ3jzRLydZPoEhRbbjREWcsUMHBGTEaoGHS3sYK
```

### Getting Started

* Create venv:
```
python3 -m venv .venv
```

* Source venv:
```
source .venv/bin/activate
```

* Install requirements:
```
pip install -r requirements.txt
```

* Source environment vars:
```
(.venv) ➜  coin-tools git:(main) cat ~/.ssh/coin-tools.env
#!/bin/bash

export COINTOOLS_DB_PATH="<PATH TO SQLITE FILE>"
export COINTOOLS_ENC_KEY="<FERNET KEY FOR ENCRYPTION OF PRIVATE KEYS>"
export COINTOOLS_RPC_URL="<SOLANA RPC>"
(.venv) ➜  coin-tools git:(main) ✗ source  ~/.ssh/coin-tools.env
```

* Run (use --help to explore):
```
(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools --help
usage: coin-tools [-h] {wallets,balances,transfers} ...

Tools for working on the Solana blockchain.

positional arguments:
  {wallets,balances,transfers}
                        Sub-commands
    wallets             Manage wallets (create, list, get, import).
    balances            View SOL and SPL token balances.
    transfers           Transfer SOL or tokens between wallets.

optional arguments:
  -h, --help            show this help message and exit


(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools balances --help
usage: coin-tools balances [-h] {get-sol-balance,get-token-balance,get-total-balance} ...

positional arguments:
  {get-sol-balance,get-token-balance,get-total-balance}
    get-sol-balance     Get the SOL balance for a wallet.
    get-token-balance   Get the balance for a specific SPL token in a wallet.
    get-total-balance   Get the total balance for all wallets.

optional arguments:
  -h, --help            show this help message and exit


(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools balances get-sol-balance --help
usage: coin-tools balances get-sol-balance [-h] --id ID

optional arguments:
  -h, --help  show this help message and exit
  --id ID     Wallet ID.


(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools balances get-token-balance --help
usage: coin-tools balances get-token-balance [-h] --id ID [--ca CA]

optional arguments:
  -h, --help  show this help message and exit
  --id ID     Wallet ID.
  --ca CA     Token contract/mint address (CA).


(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools wallets --help
usage: coin-tools wallets [-h] {create,list,get,import,rename,ticker,encryption} ...

positional arguments:
  {create,list,get,import,rename,ticker,encryption}
    create              Create a new Solana wallet.
    list                List all wallets.
    get                 Get a single wallet by ID.
    import              Import an existing wallet from private key only.
    rename              Rename a wallet.
    ticker              Manage tickers for known tokens.
    encryption          Manage encryption settings.

optional arguments:
  -h, --help            show this help message and exit


(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools transfer --help
usage: coin-tools [-h] {wallets,balances,transfers} ...
coin-tools: error: argument command: invalid choice: 'transfer' (choose from 'wallets', 'balances', 'transfers')
(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools transfers --help
usage: coin-tools transfers [-h] {transfer-sol,transfer-token,migrate} ...

positional arguments:
  {transfer-sol,transfer-token,migrate}
    transfer-sol        Transfer SOL from one wallet to another.
    transfer-token      Transfer a token from one wallet to another.
    migrate             Migrate all SOL and tokens from one wallet to another.

optional arguments:
  -h, --help            show this help message and exit
(.venv) ➜  coin-tools git:(main) ✗
```

### Notes on encryption:
Private keys are encrypted using a fernet key which is read in as an environment variable.

To generate a new fernet key use:
```
coin-tools wallet encryption --generate-key
```
This will print a new fernet key to the console and you will need to store it in an environment variable and source it prior to using the script.

To rotate the fernet key observe the following:
```
(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools wallets encryption --generate-key
Generating a new encryption key...
<ABCEFGHIJKLMNOPQRSTUVWXYZ>
Please store this key securely.
You will need it to decrypt any data encrypted with this key.
You must set this key as the COINTOOLS_ENC_KEY environment variable.
(.venv) ➜  coin-tools git:(main) ✗ ./coin-tools wallets encryption --rotate-key
There are 50 wallets stored in this database
Rotating the encryption key will re-encrypt all private keys.
Current private keys will not be able to be read until the new key is set as COINTOOLS_ENC_KEY.
Be sure to back up the database and the current encryption key.
Please enter a new encryption key and press Enter to continue: <ABCEFGHIJKLMNOPQRSTUVWXYZ>
Rotating the encryption key...
Encryption key rotation complete.
Please set the new key as the COINTOOLS_ENC_KEY environment variable.
```

TODO (not priority order):
1. Wallet deletion (close solana account, reclaim SOL, etc)
2. Ticker from Metaplex
3. Pump Fun buy/sell
4. Volume bot