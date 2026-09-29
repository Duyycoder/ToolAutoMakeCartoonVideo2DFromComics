"""Phục vụ thư mục gốc repo để chạy tests/js trong trình duyệt (máy không có Node).

    python tests/js/trinh_duyet/phuc_vu.py      → mở http://127.0.0.1:8210/tests/js/trinh_duyet/chay.html

http.server thường trả `.mjs` với MIME text/plain trên Windows → trình duyệt từ chối nạp module.
"""
import functools
import http.server
import os

GOC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


class XuLy(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".mjs": "text/javascript", ".js": "text/javascript"}


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", 8210), functools.partial(XuLy, directory=GOC)).serve_forever()
