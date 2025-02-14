from nodetools.utilities.credentials import CredentialManager, get_credentials_directory
from xrpl.wallet import Wallet
import getpass
import json
from pathlib import Path
import xrpl

def setup_node():        
    print("\nPostFiat Node Setup")
    print("======================")
    print("This script will help you set up your node configuration and credentials.")

    # Get network type first
    while True:
        network = input("\nAre you setting up for testnet or mainnet? (testnet/mainnet): ").strip().lower()
        if network in ['testnet', 'mainnet']:
            break
        print("Please enter either 'testnet' or 'mainnet'")

    # Get node name first - this will be used for both credentials and config
    print(f"\nNext, you'll need to specify your node name.")
    print("This will be used to identify your node's credentials.")
    if network == 'testnet':
        print("Since this is testnet, a '_testnet' suffix will automatically be added to your node name. Just enter your node name without the suffix.")
    node_name = input("Enter your node name: ").strip()

    # API Key Selection
    print("\nLLM API Key Setup")
    print("=================")
    print("OpenRouter API key is required for task generation.")
    print("You can get one at https://openrouter.ai/")

    while True:
        has_openrouter = input("\nDo you have an OpenRouter API key? (y/n): ").strip().lower()
        if has_openrouter == 'y':
            break
        elif has_openrouter == 'n':
            print("\nERROR: An OpenRouter API key is required to run the node.")
            print("Please obtain one from https://openrouter.ai/ before continuing.")
            if input("Continue anyway? (y/n): ").strip().lower() != 'y':
                return
            break
        print("Please enter 'y' or 'n'")

    # TODO: Add OpenAI and Anthropic support
    # print("The following API keys are supported (OpenRouter recommended):")
    # print("1. OpenRouter - Recommended, provides access to multiple LLMs")
    # print("2. OpenAI    - Direct GPT access")
    # print("3. Anthropic - Direct Claude access")

    # has_openrouter = input("\nDo you have an OpenRouter API key? (y/n): ").strip().lower() == 'y'
    # has_openai = input("Do you have an OpenAI API key? (y/n): ").strip().lower() == 'y'
    # has_anthropic = input("Do you have an Anthropic API key? (y/n): ").strip().lower() == 'y'

    # if not any([has_openrouter, has_openai, has_anthropic]):
    #     print("\nWARNING: At least one LLM API key is required for task generation.")
    #     print("Please obtain an API key (preferably OpenRouter) before continuing.")
    #     if input("Continue anyway? (y/n): ").strip().lower() != 'y':
    #         return

    has_remembrancer = input("\nDo you have a remembrancer wallet for your node? (y/n): ").strip().lower() == 'y'
    has_discord = input("Do you want to set up a Discord guild? (y/n): ").strip().lower() == 'y'

    network_suffix = '_testnet' if network == 'testnet' else ''

    required_credentials = {
        f'{node_name}{network_suffix}__v1xrpsecret': 'Your PFT Foundation XRP Secret',
        f'{node_name}{network_suffix}_postgresconnstring': 'PostgreSQL connection string',
        'openrouter': 'Your OpenRouter API Key (from openrouter.ai)'
    }

    # # Add selected API keys
    # if has_openrouter:
    #     required_credentials['openrouter'] = 'Your OpenRouter API Key (from openrouter.ai)'
    # if has_openai:
    #     required_credentials['openai'] = 'Your OpenAI API Key'
    # if has_anthropic:
    #     required_credentials['anthropic'] = 'Your Anthropic API Key'

    # Conditionally add remembrancer credentials
    if has_remembrancer:
        required_credentials[f'{node_name}{network_suffix}_remembrancer__v1xrpsecret'] = 'Your Remembrancer XRP Secret'

    # Conditionally add Discord credentials
    if has_discord:
        required_credentials[f'discordbot{network_suffix}_secret'] = 'Your Discord Bot Token'

    schema_extensions = []
    has_custom_extension = input("\nDo you have any custom SQL database schema extensions? (y/n): ").strip().lower() == 'y'
    if has_custom_extension:
        while True:
            extension_path = input("\nEnter the full import path (e.g., myapp.extensions.CustomExtension): ").strip()
            if extension_path:
                schema_extensions.append(extension_path)
            
            if input("Add another extension? (y/n): ").strip().lower() != 'y':
                break

    print("\nNow you'll need to enter a password to encrypt your credentials.\n")
    
    # Get encryption password
    while True:
        encryption_password = getpass.getpass("Enter an encryption password (min 8 characters): ")
        if len(encryption_password) >= 8:
            confirm_password = getpass.getpass("Confirm encryption password: ")
            if encryption_password == confirm_password:
                break
            else:
                print("Passwords don't match. Please try again.\n")
        else:
            print("Password must be at least 8 characters long. Please try again.\n")
    
    print("\nNow you'll need to enter each required credential.")
    print("These will be encrypted using your password.\n")

    # Initialize the credential manager
    cm : CredentialManager = CredentialManager(encryption_password)

    # Collect credentials into a dictionary
    credentials_dict = {}

    config = {
        'node_name': f"{node_name}{network_suffix}",
        'auto_handshake_addresses': []
    }
    
    # Collect and encrypt each credential
    for cred_name, description in required_credentials.items():
        print(f"\nSetting up: {cred_name}")
        print(f"Description: {description}")

        while True:
            # Add special instructions for PostgreSQL connection string
            if 'postgresconnstring' in cred_name:
                db_name = 'postfiat_db_testnet' if network == 'testnet' else 'postfiat_db'
                print("\nLet's build your PostgreSQL connection string.")
                print("Default values will be shown in [brackets]. Press Enter to use them.")
                
                user = input("PostgreSQL username [postfiat]: ").strip() or "postfiat"
                password = input("PostgreSQL password: ").strip()
                host = input("Database host [localhost]: ").strip() or "localhost"
                port = input("Database port [5432]: ").strip() or "5432"
                
                credential_value = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
                print(f"\nConnection string created with database: {db_name}")
                print(f"Connection string: {credential_value}")
                print("The database will be created automatically when you run `nodetools init-db`")
                credentials_dict[cred_name] = credential_value
                break

            else:
                credential_value = input(f"Enter value for {cred_name}: ").strip()

                if credential_value:
                    try:
                        credentials_dict[cred_name] = credential_value
                        break
                    except Exception as e:
                        print(f"Error storing credential: {str(e)}")
                        retry = input("Would you like to try again? (y/n): ")
                        if retry.lower() != 'y':
                            break
                else:
                    print("Credential cannot be empty. Please try again.")
    
    # Set up node address from main wallet
    node_wallet = xrpl.wallet.Wallet.from_seed(credentials_dict[f'{node_name}{network_suffix}__v1xrpsecret'])
    config['node_address'] = node_wallet.classic_address

    # If remembrancer credentials were collected, add to config
    if has_remembrancer:
        remembrancer_wallet = xrpl.wallet.Wallet.from_seed(seed=credentials_dict[f'{node_name}{network_suffix}_remembrancer__v1xrpsecret'])
        config['remembrancer_name'] = f"{node_name}{network_suffix}_remembrancer"
        config['remembrancer_address'] = remembrancer_wallet.classic_address

    # If Discord was set up, add guild configuration
    if has_discord:
        print("\nDiscord Configuration")
        print("====================")
        config['discord_guild_id'] = int(input("Enter Discord guild ID: ").strip())
        config['discord_activity_channel_id'] = int(input("Enter Discord activity channel ID: ").strip())

    if schema_extensions:
        config['schema_extensions'] = schema_extensions

    # Save node configuration
    config_dir = get_credentials_directory()
    config_file = config_dir / f"pft_node_{'testnet' if network == 'testnet' else 'mainnet'}_config.json"

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    # Store all credentials at once
    try:
        cm.enter_and_encrypt_credential(credentials_dict)
        print("\nCredential setup complete!")
        print(f"Credentials stored in: {cm.db_path}")
        print(f"Node configuration stored in: {config_file}")
        print("\nIMPORTANT: Keep your encryption password safe. You'll need it to run the bot.")
        print("When starting the bot, enter this same encryption password when prompted.")
    except Exception as e:
        print(f"\nError storing credentials: {str(e)}")

def main():
    try:
        setup_node()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")

if __name__ == "__main__":
    main()