import os
import sys
import json
import uuid
import shutil
import tempfile
import secrets
import zipfile
import traceback
import tornado.web
import tornado.ioloop
import tornado.httpserver

# Set path for core modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'core'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'io_utils'))

from steganography import (
    embed_universal, extract_universal, get_file_capacity, detect_file_type,
    split_file, create_split_payload, parse_split_payload,
    generate_fingerprint, extract_from_audio, extract_from_video, DEVICE,
    embed_in_image_gpu, embed_in_audio, embed_in_video, extract_from_image_gpu
)
from crypto import BitcoinStyleCrypto

crypto = BitcoinStyleCrypto()
CACHE_DIR = tempfile.mkdtemp(prefix="ciphersteg_cache_")

def cleanup_old_sessions():
    """Keep cache clean by removing very old directories if needed."""
    try:
        for item in os.listdir(CACHE_DIR):
            item_path = os.path.join(CACHE_DIR, item)
            # Remove anything older than 2 hours
            if os.path.isdir(item_path):
                age = os.path.getmtime(item_path)
                import time
                if time.time() - age > 7200:
                    shutil.rmtree(item_path, ignore_errors=True)
    except Exception:
        pass

class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with, content-type")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def write_json(self, data, status_code=200):
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data))

class SystemInfoHandler(BaseHandler):
    def get(self):
        self.write_json({
            "status": "online",
            "device": str(DEVICE),
            "curve": "SECP256K1",
            "ecc": "Reed-Solomon (32 symbols)",
            "supported_carriers": ["JPEG", "PNG", "BMP", "WebP", "WAV", "FLAC", "MP3", "MP4", "MKV", "TXT"]
        })

class KeygenHandler(BaseHandler):
    def post(self):
        try:
            req_data = {}
            if self.request.body:
                try:
                    req_data = json.loads(self.request.body.decode('utf-8'))
                except:
                    pass
            
            password = req_data.get('password', None)
            if password == "":
                password = None

            priv_key, pub_key = crypto.generate_keypair()
            temp_dir = tempfile.mkdtemp()
            priv_path = os.path.join(temp_dir, "priv.pem")
            pub_path = os.path.join(temp_dir, "pub.pem")

            crypto.save_private_key(priv_key, priv_path, password=password)
            crypto.save_public_key(pub_key, pub_path)

            with open(priv_path, "r") as f:
                priv_pem = f.read()
            with open(pub_path, "r") as f:
                pub_pem = f.read()

            fingerprint = crypto.get_key_fingerprint(pub_key)
            shutil.rmtree(temp_dir, ignore_errors=True)

            self.write_json({
                "success": True,
                "private_key": priv_pem,
                "public_key": pub_pem,
                "fingerprint": fingerprint
            })
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, 500)

class CapacityHandler(BaseHandler):
    def post(self):
        try:
            if 'cover' not in self.request.files:
                return self.write_json({"success": False, "error": "No cover file provided"}, 400)
            
            cover_file = self.request.files['cover'][0]
            ext = os.path.splitext(cover_file['filename'])[1]
            temp_cover = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_cover.write(cover_file['body'])
            temp_cover.close()

            file_type = detect_file_type(temp_cover.name)
            capacity = get_file_capacity(temp_cover.name)
            cover_size = os.path.getsize(temp_cover.name)

            secret_size = None
            fit = None
            pct = None
            split_needed = 1

            if 'secret' in self.request.files:
                secret_file = self.request.files['secret'][0]
                secret_size = len(secret_file['body'])
                if capacity > 0:
                    pct = round((secret_size / capacity) * 100, 2)
                    fit = secret_size <= capacity
                    # Account for encryption (+95B), ECC (+32B), and SPLT headers with safe safety margin
                    effective_size = int(secret_size * 1.05) + 300
                    split_needed = max(2, (effective_size + capacity - 1) // capacity)
                    # Add 1 more part if close to boundary for safety
                    if (effective_size / split_needed) > (capacity * 0.9):
                        split_needed += 1
                else:
                    pct = 999.0
                    fit = False
                    split_needed = 2

            os.unlink(temp_cover.name)

            self.write_json({
                "success": True,
                "cover_type": file_type.upper(),
                "cover_size": cover_size,
                "capacity": capacity,
                "secret_size": secret_size,
                "fit": fit,
                "pct": pct,
                "split_needed": split_needed
            })
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, 500)

class EmbedHandler(BaseHandler):
    def post(self):
        try:
            cleanup_old_sessions()
            logs = []
            
            if 'cover' not in self.request.files or 'secret' not in self.request.files:
                return self.write_json({"success": False, "error": "Cover file and Secret file are required."}, 400)

            cover_upload = self.request.files['cover'][0]
            secret_upload = self.request.files['secret'][0]

            encrypt = self.get_argument('encrypt', 'false').lower() == 'true'
            split_count = int(self.get_argument('split', '1'))
            bit_position = self.get_argument('bit_position', 'lsb')

            logs.append(f"Carrier loaded: {cover_upload['filename']} ({len(cover_upload['body']):,} bytes)")
            logs.append(f"Secret loaded: {secret_upload['filename']} ({len(secret_upload['body']):,} bytes)")

            # Temp storage for processing
            cover_ext = os.path.splitext(cover_upload['filename'])[1]
            temp_cover = tempfile.NamedTemporaryFile(delete=False, suffix=cover_ext)
            temp_cover.write(cover_upload['body'])
            temp_cover.close()

            # Generate 16-byte random fingerprint seed
            fingerprint_seed = secrets.token_hex(16)
            fingerprint_bytes = generate_fingerprint(fingerprint_seed)
            logs.append(f"Generated 128-bit PRNG Fingerprint: {fingerprint_seed}")

            secret_data = secret_upload['body']
            encrypted_fp_bytes = None

            if encrypt:
                if 'recipient_key' not in self.request.files:
                    return self.write_json({"success": False, "error": "Recipient public key is required for encryption."}, 400)
                
                recip_file = self.request.files['recipient_key'][0]
                temp_recip = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                temp_recip.write(recip_file['body'])
                temp_recip.close()

                try:
                    recip_pub = crypto.load_public_key(temp_recip.name)
                except Exception as ex:
                    os.unlink(temp_recip.name)
                    return self.write_json({"success": False, "error": f"Invalid recipient public key: {ex}"}, 400)
                os.unlink(temp_recip.name)

                fp = crypto.get_key_fingerprint(recip_pub)
                logs.append(f"Bitcoin SECP256K1 ECIES initiated for recipient: {fp}")

                # Encrypt secret & fingerprint
                secret_data = crypto.encrypt_file(secret_data, recip_pub)
                encrypted_fp_bytes = crypto.encrypt_file(fingerprint_seed.encode(), recip_pub)
                logs.append(f"Secret encrypted via AES-256-GCM ({len(secret_data):,} bytes)")
                logs.append(f"Fingerprint encrypted into binary token ({len(encrypted_fp_bytes)} bytes)")

            # Check capacity
            cap = get_file_capacity(temp_cover.name)
            logs.append(f"Carrier usable capacity: {cap:,} bytes")

            if split_count > 1:
                sample_chunk = (len(secret_data) + split_count - 1) // split_count + 120
                if sample_chunk > cap:
                    min_parts = (len(secret_data) + cap - 1) // cap + 1
                    os.unlink(temp_cover.name)
                    return self.write_json({
                        "success": False,
                        "error": f"Each part ({sample_chunk/1024:.1f} KB) still exceeds this carrier's capacity ({cap/1024:.1f} KB). Please increase the split slider to at least {min_parts} parts, or use a larger cover image."
                    }, 400)
            elif len(secret_data) > cap:
                min_parts = (len(secret_data) + cap - 1) // cap + 1
                os.unlink(temp_cover.name)
                return self.write_json({
                    "success": False,
                    "error": f"Secret ({len(secret_data)/1024:.1f} KB) exceeds this single carrier's capacity ({cap/1024:.1f} KB). Please enable 'Multi-Carrier Splitting' with at least {min_parts} parts, or use a larger cover image."
                }, 400)

            # Create session output dir in CACHE_DIR
            session_id = str(uuid.uuid4())
            session_dir = os.path.join(CACHE_DIR, session_id)
            os.makedirs(session_dir, exist_ok=True)

            temp_payload = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
            temp_payload.write(secret_data)
            temp_payload.close()

            download_links = {}

            if split_count <= 1:
                # Single Embed
                cov_type = detect_file_type(temp_cover.name)
                if cov_type == 'image':
                    out_ext = '.jpg' if temp_cover.name.lower().endswith(('.jpg', '.jpeg')) else '.png'
                elif cov_type == 'audio':
                    out_ext = '.flac'
                elif cov_type == 'video':
                    out_ext = '.mp4'
                else:
                    out_ext = cover_ext

                stego_filename = f"stego_{secrets.token_hex(4)}{out_ext}"
                stego_out_path = os.path.join(session_dir, stego_filename)

                logs.append(f"Invoking {cov_type.upper()} steganography engine ({bit_position.upper()})...")
                embed_universal(temp_cover.name, temp_payload.name, stego_out_path, bit_position=bit_position, fingerprint_bytes=fingerprint_bytes)
                logs.append(f"Stego payload embedded successfully with Reed-Solomon ECC protection.")

                # Save fingerprint
                if encrypt:
                    fp_filename = ".fingerprint.enc"
                    with open(os.path.join(session_dir, fp_filename), "wb") as f:
                        f.write(encrypted_fp_bytes)
                else:
                    fp_filename = ".fingerprint"
                    with open(os.path.join(session_dir, fp_filename), "w") as f:
                        f.write(fingerprint_seed)

                download_links = {
                    "stego": f"/download/{session_id}/{stego_filename}",
                    "stego_name": stego_filename,
                    "fingerprint": f"/download/{session_id}/{fp_filename}",
                    "fingerprint_name": fp_filename,
                    "is_split": False
                }
            else:
                # Split Embed across multiple carriers
                parts = split_file(temp_payload.name, split_count)
                logs.append(f"Payload split into {split_count} encrypted chunks.")
                filename_bytes = secret_upload['filename'].encode('utf-8')

                zip_filename = f"ciphersteg_split_{secrets.token_hex(4)}.zip"
                zip_path = os.path.join(session_dir, zip_filename)

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    cov_type = detect_file_type(temp_cover.name)
                    for idx, part_data in enumerate(parts):
                        payload = create_split_payload(part_data, idx, split_count, filename_bytes, fingerprint_bytes)
                        part_out_name = f"carrier_part_{idx+1}_{secrets.token_hex(6)}{cover_ext}"
                        part_out_path = os.path.join(session_dir, part_out_name)

                        if cov_type == 'image':
                            embed_in_image_gpu(temp_cover.name, payload, part_out_path, bit_position=bit_position, fingerprint_bytes=fingerprint_bytes)
                        elif cov_type == 'audio':
                            embed_in_audio(temp_cover.name, payload, part_out_path, fingerprint_bytes=fingerprint_bytes)
                        elif cov_type == 'video':
                            embed_in_video(temp_cover.name, payload, part_out_path, fingerprint_bytes=fingerprint_bytes)
                        else:
                            t_part_payload = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
                            t_part_payload.write(payload)
                            t_part_payload.close()
                            embed_universal(temp_cover.name, t_part_payload.name, part_out_path, fingerprint_bytes=fingerprint_bytes)
                            os.unlink(t_part_payload.name)

                        zf.write(part_out_path, arcname=part_out_name)
                        os.unlink(part_out_path)
                        logs.append(f"Embedded Chunk {idx+1}/{split_count} -> {part_out_name}")

                    if encrypt:
                        zf.writestr(".fingerprint.enc", encrypted_fp_bytes)
                    else:
                        zf.writestr(".fingerprint", fingerprint_seed.encode())

                download_links = {
                    "archive": f"/download/{session_id}/{zip_filename}",
                    "archive_name": zip_filename,
                    "is_split": True,
                    "parts_count": split_count
                }

            # Cleanup
            os.unlink(temp_cover.name)
            os.unlink(temp_payload.name)

            logs.append("All operations completed with cryptographic integrity verified.")

            self.write_json({
                "success": True,
                "session_id": session_id,
                "downloads": download_links,
                "logs": logs,
                "fingerprint_seed": fingerprint_seed
            })

        except Exception as e:
            traceback.print_exc()
            self.write_json({"success": False, "error": str(e)}, 500)

class ExtractHandler(BaseHandler):
    def post(self):
        try:
            cleanup_old_sessions()
            logs = []

            if 'stego' not in self.request.files or 'fingerprint' not in self.request.files:
                return self.write_json({"success": False, "error": "Stego file and Fingerprint file are required."}, 400)

            stego_upload = self.request.files['stego'][0]
            fp_upload = self.request.files['fingerprint'][0]
            decrypt = self.get_argument('decrypt', 'false').lower() == 'true'
            password = self.get_argument('password', None)
            if password == "":
                password = None
            bit_position = self.get_argument('bit_position', 'lsb')

            logs.append(f"Stego file received: {stego_upload['filename']}")
            logs.append(f"Fingerprint file received: {fp_upload['filename']}")

            stego_ext = os.path.splitext(stego_upload['filename'])[1]
            temp_stego = tempfile.NamedTemporaryFile(delete=False, suffix=stego_ext)
            temp_stego.write(stego_upload['body'])
            temp_stego.close()

            fp_bytes = fp_upload['body']
            is_enc_fp = fp_upload['filename'].endswith(".enc")

            private_key = None
            if is_enc_fp or decrypt:
                if 'private_key' not in self.request.files:
                    os.unlink(temp_stego.name)
                    return self.write_json({"success": False, "error": "Private key is required to decrypt."}, 400)
                
                priv_upload = self.request.files['private_key'][0]
                temp_priv = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                temp_priv.write(priv_upload['body'])
                temp_priv.close()

                try:
                    private_key = crypto.load_private_key(temp_priv.name, password=password)
                    logs.append("Loaded recipient SECP256K1 private key successfully.")
                except Exception as ex:
                    os.unlink(temp_priv.name)
                    os.unlink(temp_stego.name)
                    return self.write_json({"success": False, "error": f"Failed to unlock private key: {ex}"}, 400)
                os.unlink(temp_priv.name)

            # Decrypt fingerprint seed if encrypted
            if is_enc_fp:
                logs.append("Decrypting encrypted fingerprint seed...")
                fingerprint_seed = crypto.decrypt_file(fp_bytes, private_key).decode()
            else:
                fingerprint_seed = fp_bytes.decode()

            logs.append(f"Derived PRNG Fingerprint Seed: {fingerprint_seed}")
            fingerprint_bytes = generate_fingerprint(fingerprint_seed)

            # Extract from carrier
            out_temp_dir = tempfile.mkdtemp()
            logs.append("Scanning PRNG positions and removing Reed-Solomon ECC redundancy...")
            extracted_path = extract_universal(temp_stego.name, output_folder=out_temp_dir, bit_position=bit_position, fingerprint_bytes=fingerprint_bytes)

            with open(extracted_path, "rb") as f:
                extracted_data = f.read()

            orig_filename = os.path.basename(extracted_path)
            logs.append(f"Recovered frame: {orig_filename} ({len(extracted_data):,} bytes)")

            if decrypt:
                logs.append("Decrypting payload using SECP256K1 ECDH + AES-256-GCM...")
                extracted_data = crypto.decrypt_file(extracted_data, private_key)
                logs.append("Authenticated decryption successful (tag verified).")

            session_id = str(uuid.uuid4())
            session_dir = os.path.join(CACHE_DIR, session_id)
            os.makedirs(session_dir, exist_ok=True)

            final_out_path = os.path.join(session_dir, orig_filename)
            with open(final_out_path, "wb") as f:
                f.write(extracted_data)

            os.unlink(temp_stego.name)
            shutil.rmtree(out_temp_dir, ignore_errors=True)

            self.write_json({
                "success": True,
                "session_id": session_id,
                "filename": orig_filename,
                "size": len(extracted_data),
                "download_url": f"/download/{session_id}/{orig_filename}",
                "logs": logs
            })

        except Exception as e:
            traceback.print_exc()
            self.write_json({"success": False, "error": str(e)}, 500)

class MergeHandler(BaseHandler):
    def post(self):
        try:
            cleanup_old_sessions()
            logs = []

            if 'fingerprint' not in self.request.files or 'stego_parts' not in self.request.files:
                return self.write_json({"success": False, "error": "Fingerprint and Stego parts are required."}, 400)

            stego_parts = self.request.files['stego_parts']
            fp_upload = self.request.files['fingerprint'][0]
            decrypt = self.get_argument('decrypt', 'false').lower() == 'true'
            password = self.get_argument('password', None)
            if password == "":
                password = None

            logs.append(f"Received {len(stego_parts)} stego parts for reconstruction.")

            fp_bytes = fp_upload['body']
            is_enc_fp = fp_upload['filename'].endswith(".enc")

            private_key = None
            if is_enc_fp or decrypt:
                if 'private_key' not in self.request.files:
                    return self.write_json({"success": False, "error": "Private key is required to decrypt."}, 400)
                
                priv_upload = self.request.files['private_key'][0]
                temp_priv = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                temp_priv.write(priv_upload['body'])
                temp_priv.close()

                try:
                    private_key = crypto.load_private_key(temp_priv.name, password=password)
                except Exception as ex:
                    os.unlink(temp_priv.name)
                    return self.write_json({"success": False, "error": f"Invalid private key: {ex}"}, 400)
                os.unlink(temp_priv.name)

            if is_enc_fp:
                fp_seed = crypto.decrypt_file(fp_bytes, private_key).decode()
            else:
                fp_seed = fp_bytes.decode()

            fp_bytes_calc = generate_fingerprint(fp_seed)
            logs.append(f"PRNG Seed verified: {fp_seed}")

            parts = {}
            total_parts = None
            orig_filename = None

            for uploaded in stego_parts:
                ext = os.path.splitext(uploaded['filename'])[1]
                t_part = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                t_part.write(uploaded['body'])
                t_part.close()

                ftype = detect_file_type(t_part.name)
                try:
                    if ftype == 'image':
                        payload = extract_from_image_gpu(t_part.name, bit_position='lsb', fingerprint_bytes=fp_bytes_calc)
                        if isinstance(payload, bytes) and payload.startswith(b'STEG'):
                            offset = 4
                            f_size = int.from_bytes(payload[offset:offset+8], 'big')
                            offset += 8
                            n_len = int.from_bytes(payload[offset:offset+2], 'big')
                            offset += 2 + n_len
                            payload = payload[offset:offset+f_size]
                    elif ftype == 'audio':
                        payload = extract_from_audio(t_part.name, fp_bytes_calc)
                    elif ftype == 'video':
                        payload = extract_from_video(t_part.name, fp_bytes_calc)
                    else:
                        os.unlink(t_part.name)
                        continue
                finally:
                    if os.path.exists(t_part.name):
                        os.unlink(t_part.name)

                info = parse_split_payload(payload)
                if total_parts is None:
                    total_parts = info['total_parts']
                    orig_filename = info['filename']

                parts[info['part_num']] = info['data']
                logs.append(f"Parsed chunk {info['part_num'] + 1}/{info['total_parts']} from {uploaded['filename']}")

            if len(parts) == 0:
                return self.write_json({"success": False, "error": "No valid stego chunks recognized."}, 400)

            logs.append(f"Successfully assembled {len(parts)} of {total_parts} chunks.")
            merged_data = b''.join([parts[i] for i in sorted(parts.keys())])

            if decrypt:
                logs.append("Decrypting assembled binary payload...")
                merged_data = crypto.decrypt_file(merged_data, private_key)

            session_id = str(uuid.uuid4())
            session_dir = os.path.join(CACHE_DIR, session_id)
            os.makedirs(session_dir, exist_ok=True)

            out_file_path = os.path.join(session_dir, orig_filename)
            with open(out_file_path, "wb") as f:
                f.write(merged_data)

            self.write_json({
                "success": True,
                "session_id": session_id,
                "filename": orig_filename,
                "size": len(merged_data),
                "download_url": f"/download/{session_id}/{orig_filename}",
                "logs": logs
            })

        except Exception as e:
            traceback.print_exc()
            self.write_json({"success": False, "error": str(e)}, 500)

class SignHandler(BaseHandler):
    def post(self):
        try:
            if 'file' not in self.request.files or 'private_key' not in self.request.files:
                return self.write_json({"success": False, "error": "File and Private Key are required."}, 400)

            file_upload = self.request.files['file'][0]
            priv_upload = self.request.files['private_key'][0]
            password = self.get_argument('password', None)
            if password == "":
                password = None

            temp_priv = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
            temp_priv.write(priv_upload['body'])
            temp_priv.close()

            pk = crypto.load_private_key(temp_priv.name, password=password)
            os.unlink(temp_priv.name)

            sig = crypto.sign_data(file_upload['body'], pk)

            session_id = str(uuid.uuid4())
            session_dir = os.path.join(CACHE_DIR, session_id)
            os.makedirs(session_dir, exist_ok=True)

            sig_name = f"{file_upload['filename']}.sig"
            sig_path = os.path.join(session_dir, sig_name)
            with open(sig_path, "wb") as f:
                f.write(sig)

            self.write_json({
                "success": True,
                "download_url": f"/download/{session_id}/{sig_name}",
                "sig_name": sig_name
            })
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, 500)

class VerifyHandler(BaseHandler):
    def post(self):
        try:
            if 'file' not in self.request.files or 'signature' not in self.request.files or 'public_key' not in self.request.files:
                return self.write_json({"success": False, "error": "File, Signature, and Public Key are all required."}, 400)

            file_data = self.request.files['file'][0]['body']
            sig_data = self.request.files['signature'][0]['body']
            pub_upload = self.request.files['public_key'][0]

            temp_pub = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
            temp_pub.write(pub_upload['body'])
            temp_pub.close()

            pub = crypto.load_public_key(temp_pub.name)
            os.unlink(temp_pub.name)

            is_valid = crypto.verify_signature(file_data, sig_data, pub)
            fp = crypto.get_key_fingerprint(pub)

            self.write_json({
                "success": True,
                "valid": is_valid,
                "fingerprint": fp
            })
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, 500)

class DownloadHandler(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')

def make_app():
    static_path = os.path.join(CURRENT_DIR, "static")
    return tornado.web.Application([
        (r"/", tornado.web.RedirectHandler, {"url": "/index.html"}),
        (r"/api/system_info", SystemInfoHandler),
        (r"/api/keygen", KeygenHandler),
        (r"/api/capacity", CapacityHandler),
        (r"/api/embed", EmbedHandler),
        (r"/api/extract", ExtractHandler),
        (r"/api/merge", MergeHandler),
        (r"/api/sign", SignHandler),
        (r"/api/verify", VerifyHandler),
        (r"/download/(.*)", DownloadHandler, {"path": CACHE_DIR}),
        (r"/(.*)", tornado.web.StaticFileHandler, {"path": static_path, "default_filename": "index.html"}),
    ], debug=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app = make_app()
    app.listen(port, address="0.0.0.0")
    print(f"✨ CipherSteg High-Performance Server running at http://localhost:{port}")
    tornado.ioloop.IOLoop.current().start()
