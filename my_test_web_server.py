from http.server import HTTPServer, BaseHTTPRequestHandler
import os

class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Redirect only if path is root
        if self.path == '/' or self.path == '':
            self.send_response(302)
            self.send_header('Location', '/portfolio')
            self.end_headers()
            return

        # Remove query string and normalize path
        path = self.path.split('?', 1)[0]
        if path == '/portfolio' or path == '/portfolio/':
            file_path = os.path.join(os.getcwd(), 'portfolio', 'index.html')
        else:
            file_path = os.path.join(os.getcwd(), path.lstrip('/'))

        # Serve HTML, CSS, JS, and image files, never show directory listings
        if os.path.isfile(file_path):
            if file_path.endswith('.html'):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
            elif file_path.endswith('.css'):
                self.send_response(200)
                self.send_header('Content-type', 'text/css')
            elif file_path.endswith('.js'):
                self.send_response(200)
                self.send_header('Content-type', 'application/javascript')
            elif file_path.endswith('.png'):
                self.send_response(200)
                self.send_header('Content-type', 'image/png')
            elif file_path.endswith('.svg'):
                self.send_response(200)
                self.send_header('Content-type', 'image/svg+xml')
            elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
            elif file_path.endswith('.gif'):
                self.send_response(200)
                self.send_header('Content-type', 'image/gif')
            elif file_path.endswith('.webp'):
                self.send_response(200)
                self.send_header('Content-type', 'image/webp')
            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'404 File Not Found')
                return
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'404 File Not Found')

if __name__ == '__main__':
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, RedirectHandler)
    print("Serving on port 8080...")
    httpd.serve_forever()