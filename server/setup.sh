#!/bin/bash

echo "========================================="
echo "Gomoku Hackathon - Quick Setup"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "server.py" ]; then
    echo "ERROR: Please run this script from the gomoku-server directory"
    exit 1
fi

echo "Step 1: Installing server dependencies..."
pip install -r requirements.txt

echo ""
echo "Step 2: Server is ready!"
echo ""
echo "To start the server, run:"
echo "  python server.py"
echo ""
echo "The server will be available at:"
echo "  - Web UI: http://localhost:8765"
echo "  - WebSocket: ws://localhost:8765/ws"
echo ""
echo "========================================="
echo "Next Steps:"
echo "========================================="
echo ""
echo "1. Start the server:"
echo "   python server.py"
echo ""
echo "2. Open the web interface:"
echo "   Open http://localhost:8765 in your browser"
echo ""
echo "3. Register a bot:"
echo "   curl -X POST 'http://localhost:8765/register?username=mybot&is_bot=true'"
echo ""
echo "4. Set up the bot template:"
echo "   cd ../gomoku-bot-template"
echo "   pip install -r requirements.txt"
echo "   # Edit bot.py to add your token and username"
echo "   python bot.py"
echo ""
echo "========================================="
echo "Happy hacking!"
echo "========================================="
