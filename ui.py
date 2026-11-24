#!/usr/bin/env python3
"""
CIPHERSTEG // High-Performance Steganography & Bitcoin Crypto Web UI Launcher
"""
import os
import sys
import socket
import webbrowser
import threading
import time

# Ensure root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)
sys.path.insert(0, os.path.join(CURRENT_DIR, 'core'))
sys.path.insert(0, os.path.join(CURRENT_DIR, 'web'))

from web.server import make_app
import tornado.ioloop

def find_available_port(start_port=8080, max_attempts=50):
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', p)) != 0:
                return p
    return start_port

def open_browser(url):
    time.sleep(0.8)
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    port = find_available_port(8080)
    url = f"http://localhost:{port}"

    print("=" * 68)
    print("  🛡️  CIPHERSTEG // UNIVERSAL STEGANOGRAPHY & CRYPTO WORKBENCH")
    print("=" * 68)
    print(f"  ► Local Web Interface:  {url}")
    print("  ► Crypto Protocol:      SECP256K1 Bitcoin Curve + AES-256-GCM")
    print("  ► Error Correction:     Reed-Solomon (32 parity symbols)")
    print("  ► Steganography:        F5 (DCT), Phase Coding, H.264, LSB")
    print("=" * 68)
    print("  Starting server and launching browser... (Press Ctrl+C to stop)")
    print()

    app = make_app()
    app.listen(port, address="0.0.0.0")

    # Launch browser in background thread
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        print("\n\nShutting down CipherSteg server. Goodbye!")
        tornado.ioloop.IOLoop.current().stop()

if __name__ == '__main__':
    main()
