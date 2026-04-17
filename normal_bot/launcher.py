import json
import requests
import os
import sys

CONFIG_FILE = "config.json"

def load_config():
    """Load configuration from config.json"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "server_url": "ws://localhost:8765/ws",
        "username": "",
        "token": ""
    }

def save_config(config):
    """Save configuration to config.json"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"\n✓ Configuration saved to {CONFIG_FILE}")

def create_account():
    """Create a new bot account"""
    config = load_config()
    
    print("\n=== Create New Bot Account ===")
    print("Note: The server must be running before creating an account.")
    print("      Test in your browser first: http://localhost:8765")
    
    # Get server URL
    server_url = input(f"\nServer URL (default: http://localhost:8765): ").strip()
    if not server_url:
        server_url = "http://localhost:8765"
    
    # Get username
    username = input("Enter bot username: ").strip()
    if not username:
        print("✗ Username cannot be empty")
        return
    
    # Register with server
    try:
        print(f"\nConnecting to {server_url}...")
        response = requests.post(f"{server_url}/register", params={"username": username, "is_bot": "true"}, timeout=5)
        data = response.json()
        
        if "error" in data:
            print(f"\n✗ Error: {data['error']}")
            return
        
        # Save credentials
        ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        config["server_url"] = ws_url
        config["username"] = data["username"]
        config["token"] = data["token"]
        save_config(config)
        
        print(f"\n✓ Account created successfully!")
        print(f"  Username: {data['username']}")
        print(f"  Token: {data['token']}")
        
    except requests.exceptions.Timeout:
        print(f"\n✗ Error: Request timed out after 5 seconds")
        print(f"  The server at {server_url} is not responding.")
        print(f"\n  Troubleshooting:")
        print(f"  1. Check if server is running: python server.py")
        print(f"  2. Try accessing in browser: {server_url}")
        print(f"  3. If on different computer, use IP address: http://192.168.x.x:8765")
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Error: Could not connect to server at {server_url}")
        print(f"  The server is not accessible at this address.")
        print(f"\n  Troubleshooting:")
        print(f"  1. Check if server is running: python server.py")
        print(f"  2. Try accessing in browser: {server_url}")
        print(f"  3. If on different computer, use IP address: http://192.168.x.x:8765")
        print(f"  4. Try http://127.0.0.1:8000 instead of localhost")
    except Exception as e:
        print(f"\n✗ Error: {e}")

def run_bot():
    """Run the bot with current configuration"""
    config = load_config()
    
    if not config["username"] or not config["token"]:
        print("\n✗ No credentials found!")
        print("  Please create an account first (option 1)")
        return
    
    print("\n=== Running Bot ===")
    print(f"Username: {config['username']}")
    print(f"Server: {config['server_url']}")
    print("\nStarting bot... (Press Ctrl+C to stop)\n")
    
    # Import and run the bot
    try:
        import bot
        bot.SERVER_URL = config["server_url"]
        bot.TOKEN = config["token"]
        bot.USERNAME = config["username"]
        
        import asyncio
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print("\n\n✓ Bot stopped by user")
    except Exception as e:
        print(f"\n✗ Error running bot: {e}")

def delete_credentials():
    """Delete stored credentials"""
    config = load_config()
    
    if not config["username"] or not config["token"]:
        print("\n✗ No credentials to delete")
        return
    
    print("\n=== Delete Credentials ===")
    print(f"Username: {config['username']}")
    print(f"Token: {config['token']}")
    
    confirm = input("\nAre you sure you want to delete these credentials? (yes/no): ").strip().lower()
    
    if confirm == "yes":
        config["username"] = ""
        config["token"] = ""
        save_config(config)
        print("\n✓ Credentials deleted")
    else:
        print("\n✗ Deletion cancelled")

def view_config():
    """View current configuration"""
    config = load_config()
    
    print("\n=== Current Configuration ===")
    print(f"Server URL: {config['server_url']}")
    print(f"Username: {config['username'] if config['username'] else '(not set)'}")
    print(f"Token: {config['token'] if config['token'] else '(not set)'}")

def main_menu():
    """Display main menu and handle user selection"""
    while True:
        print("\n" + "="*50)
        print("Gomoku Bot Launcher")
        print("="*50)
        
        config = load_config()
        if config["username"] and config["token"]:
            print(f"Current account: {config['username']}")
        else:
            print("Current account: (none)")
        
        print("\n1) Create a new account")
        print("2) Run the bot")
        print("3) Delete existing credentials")
        print("4) View configuration")
        print("5) Exit")
        
        choice = input("\nSelect an option (1-5): ").strip()
        
        if choice == "1":
            create_account()
        elif choice == "2":
            run_bot()
        elif choice == "3":
            delete_credentials()
        elif choice == "4":
            view_config()
        elif choice == "5":
            print("\nGoodbye!")
            sys.exit(0)
        else:
            print("\n✗ Invalid option. Please choose 1-5.")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
