# proxy_safe.py (LISTEN_PORT=8888) - có log chi tiết & nới điều kiện chèn header
# - Frontend CL-first (ưu tiên Content-Length)
# - GIỮ Transfer-Encoding để backend TE-first
# - Sau 1 request CL+TE, request KẾ TIẾP có path /admin sẽ được chèn X-Internal-Admin: 1
#   (không bắt buộc request đó phải đến 100% từ buffer)
# - Tự reconnect upstream nếu backend trả Connection: close
# - Log: path, used_only_carry, CL/TE, armed-flag, inject, server_closed

import socket
import threading
import re
import time

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8888

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 9000

CLIENT_RECV_TIMEOUT = 8.0
UPSTREAM_RECV_TIMEOUT = 10.0
IDLE_TIMEOUT = 30.0

# KHÔNG loại "transfer-encoding" để backend có thể TE-first
HOP_BY_HOP_DROP = {"proxy-connection", "connection", "keep-alive", "upgrade"}

REQUEST_LINE_RE = re.compile(rb"^([A-Z]{3,10})\s+(\S+)\s+HTTP/1\.[01]\r\n")

def set_timeouts(sock, rcv=CLIENT_RECV_TIMEOUT):
    sock.settimeout(rcv)

def recv_some(sock, bufsize=4096):
    try:
        return sock.recv(bufsize)
    except socket.timeout:
        return b""
    except Exception:
        return b""

def recv_until(sock, marker, carry=b"", max_bytes=1024*1024):
    """
    Đọc đến marker, trả (head, rest, used_only_carry)
    - used_only_carry = True nếu hoàn toàn tìm thấy trong carry (không đọc thêm từ socket)
    """
    data = bytearray(carry)
    used_socket = False
    while True:
        idx = data.find(marker)
        if idx != -1:
            head = bytes(data[:idx+len(marker)])
            rest = bytes(data[idx+len(marker):])
            used_only_carry = (not used_socket) and (len(carry) > 0)
            return head, rest, used_only_carry
        if len(data) > max_bytes:
            raise ValueError("Header quá lớn")
        chunk = recv_some(sock)
        if not chunk:
            return None, bytes(data), False
        used_socket = True
        data.extend(chunk)

def parse_headers(header_bytes):
    lines = header_bytes.split(b"\r\n")
    req_line = lines[0] + b"\r\n"
    hdrs = []
    lower_map = {}
    for raw in lines[1:]:
        if not raw:
            continue
        p = raw.find(b":")
        if p == -1:
            continue
        name = raw[:p].decode("iso-8859-1").strip()
        value = raw[p+1:].decode("iso-8859-1").strip()
        hdrs.append((name, value))
        lower_map[name.lower()] = value
    return req_line, hdrs, lower_map

def extract_path_from_reqline(req_line_bytes):
    try:
        parts = req_line_bytes.decode("iso-8859-1").split()
        if len(parts) >= 2:
            return parts[1]
    except Exception:
        pass
    return "/"

def build_forward_headers(hdrs, xff_ip, inject_internal_admin=False):
    out = []
    saw_xff = False
    for name, value in hdrs:
        lname = name.lower()
        if lname in HOP_BY_HOP_DROP:
            continue
        if lname == "x-forwarded-for":
            saw_xff = True
            value = value + ", " + xff_ip
            out.append((name, value))
            continue
        out.append((name, value))
    out.append(("Connection", "keep-alive"))
    if not saw_xff:
        out.append(("X-Forwarded-For", xff_ip))
    if inject_internal_admin:
        out.append(("X-Internal-Admin", "1"))
    return out

def headers_to_bytes(req_line, hdrs):
    b = bytearray()
    b.extend(req_line)
    for name, value in hdrs:
        b.extend(name.encode("iso-8859-1") + b": " + value.encode("iso-8859-1") + b"\r\n")
    b.extend(b"\r\n")
    return bytes(b)

def read_exact(sock, need, carry=b""):
    data = bytearray(carry)
    while len(data) < need:
        chunk = recv_some(sock)
        if not chunk:
            break
        data.extend(chunk)
    body = bytes(data[:need])
    rest = bytes(data[need:])
    return body, rest

def parse_response_and_relay(upstream, client):
    """
    Trả (ok, conn_close_from_server)
    """
    upstream.settimeout(UPSTREAM_RECV_TIMEOUT)
    head, rest, _ = recv_until(upstream, b"\r\n\r\n")
    if not head:
        print("[proxy] upstream no head -> ok=False")
        return False, False
    client.sendall(head)

    _, hdrs, lower = parse_headers(head)
    te = lower.get("transfer-encoding", "")
    cl = lower.get("content-length")
    conn_hdr = lower.get("connection", "")
    server_wants_close = "close" in conn_hdr.lower()

    if te and "chunked" in te.lower():
        buf = bytearray(rest)
        while True:
            while b"\r\n" not in buf:
                chunk = recv_some(upstream)
                if not chunk:
                    client.sendall(bytes(buf))
                    return False, True
                buf.extend(chunk)
            line, _, tail = bytes(buf).partition(b"\r\n")
            buf = bytearray(tail)
            size_hex = line.split(b";", 1)[0].strip()
            try:
                size = int(size_hex, 16)
            except Exception:
                client.sendall(line + b"\r\n" + bytes(buf))
                return False, True
            client.sendall(line + b"\r\n")
            while len(buf) < size + 2:
                chunk = recv_some(upstream)
                if not chunk:
                    client.sendall(bytes(buf))
                    return False, True
                buf.extend(chunk)
            chunk_data = bytes(buf[:size])
            crlf = bytes(buf[size:size+2])
            buf = bytearray(buf[size+2:])
            client.sendall(chunk_data + crlf)
            if size == 0:
                if buf:
                    client.sendall(bytes(buf))
                break
        return True, server_wants_close

    if cl is not None:
        try:
            need = int(cl)
        except Exception:
            need = 0
        have = len(rest)
        if have >= need:
            client.sendall(rest[:need])
            return True, server_wants_close
        else:
            client.sendall(rest)
            remain = need - have
            body, _ = read_exact(upstream, remain)
            client.sendall(body)
            return True, server_wants_close

    # Không CL, không TE -> best-effort
    upstream.settimeout(1.0)
    client.settimeout(1.0)
    if rest:
        client.sendall(rest)
    last = time.time()
    while time.time() - last < 2.0:
        chunk = recv_some(upstream)
        if chunk:
            client.sendall(chunk)
            last = time.time()
        else:
            time.sleep(0.05)
    return True, server_wants_close

def new_upstream():
    s = socket.create_connection((BACKEND_HOST, BACKEND_PORT))
    s.settimeout(UPSTREAM_RECV_TIMEOUT)
    return s

def handle_client(client_sock, client_addr):
    set_timeouts(client_sock)
    xff_ip = client_addr[0]

    upstream = new_upstream()

    carry = b""
    inject_admin_on_next = False  # “armed” sau khi gặp CL+TE

    try:
        last_active = time.time()
        while True:
            head, carry, used_only_carry = recv_until(client_sock, b"\r\n\r\n", carry)
            if not head:
                break

            if not REQUEST_LINE_RE.match(head):
                print("[proxy] non-HTTP start-line; skipping junk")
                continue

            req_line, hdrs, lower = parse_headers(head)
            path = extract_path_from_reqline(req_line)
            has_cl = "content-length" in lower
            has_te = "transfer-encoding" in lower and "chunked" in lower.get("transfer-encoding", "").lower()
            print(f"[proxy] >>> got request path={path} used_only_carry={used_only_carry} has_cl={has_cl} has_te={has_te} armed={inject_admin_on_next}")

            # CL-first: chỉ đọc đúng số byte theo CL
            body = b""
            if has_cl:
                try:
                    need = int(lower["content-length"])
                    if need < 0:
                        need = 0
                except Exception:
                    need = 0
                if len(carry) >= need:
                    body = carry[:need]
                    carry = carry[need:]
                else:
                    missing = need - len(carry)
                    more, carry2 = read_exact(client_sock, missing)
                    body = carry + more
                    carry = carry2

            # Quyết định chèn header hay không (đÃ NỚI ĐIỀU KIỆN)
            inject_internal = False
            if inject_admin_on_next and path.startswith("/admin"):
                inject_internal = True
                inject_admin_on_next = False
            elif used_only_carry:
                # nếu request đến từ buffer nhưng không phải /admin, tiêu thụ cơ hội
                inject_admin_on_next = False
            print(f"[proxy]     inject_internal={inject_internal} (add X-Internal-Admin only if True)")

            fwd_hdrs = build_forward_headers(hdrs, xff_ip, inject_internal_admin=inject_internal)
            fwd_head = headers_to_bytes(req_line, fwd_hdrs)

            # Gửi lên upstream (reconnect nếu cần)
            try:
                upstream.sendall(fwd_head + body)
            except Exception as e:
                print(f"[proxy] upstream send failed ({e}), reconnecting...")
                try:
                    upstream.close()
                except Exception:
                    pass
                upstream = new_upstream()
                upstream.sendall(fwd_head + body)

            # Đặt cờ cho lần tới nếu đây là CL.TE
            if has_cl and has_te:
                inject_admin_on_next = True
                print("[proxy]     this was CL+TE; ARMED for next request")
            # else: giữ nguyên trạng thái

            ok, server_closed = parse_response_and_relay(upstream, client_sock)
            print(f"[proxy] <<< upstream_response ok={ok} server_closed={server_closed}")
            if not ok:
                break

            if server_closed:
                try:
                    upstream.close()
                except Exception:
                    pass
                upstream = new_upstream()
                print("[proxy] reopened upstream after server close")

            last_active = time.time()
            if time.time() - last_active > IDLE_TIMEOUT:
                break

    except Exception as e:
        print(f"[proxy] exception in handler: {e}")
    finally:
        try:
            upstream.close()
        except Exception:
            pass
        try:
            client_sock.close()
        except Exception:
            pass

def serve():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, LISTEN_PORT))
    srv.listen(128)
    print(f"[proxy] Listening on http://{LISTEN_HOST}:{LISTEN_PORT} -> upstream {BACKEND_HOST}:{BACKEND_PORT}")
    try:
        while True:
            c, addr = srv.accept()
            t = threading.Thread(target=handle_client, args=(c, addr), daemon=True)
            t.start()
    finally:
        srv.close()

if __name__ == "__main__":
    serve()
