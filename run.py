import sys
import os
import socket
import webbrowser
import uvicorn

def find_available_port(start_port=8000, max_attempts=50):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    host = "127.0.0.1"
    port = find_available_port(8000)
    url = f"http://{host}:{port}"
    
    print("=" * 60)
    print("⚡ Starting YouTube Shorts Top X% Scraper Web Application")
    print(f"🌐 Server URL: {url}")
    print("=" * 60)
    
    try:
        webbrowser.open(url)
    except Exception:
        pass

    uvicorn.run("backend.app:app", host=host, port=port, reload=True)
