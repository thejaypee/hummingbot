#!/usr/bin/env python3
"""Simple HTTP server to serve dashboard.html on port 3000."""
import http.server
import os
import socketserver

PORT = 3000
DIRECTORY = "/home/sauly/hummingbot"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


if __name__ == "__main__":
    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Dashboard server running at http://localhost:{PORT}/dashboard.html")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()
