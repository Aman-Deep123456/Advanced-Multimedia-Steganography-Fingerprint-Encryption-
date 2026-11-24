import os
import sys
import tempfile
import io
import zipfile
import streamlit as st
from PIL import Image

# Add core and io_utils to system path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'io_utils'))

from steganography import (
    embed_universal, extract_universal, get_file_capacity, detect_file_type,
    split_file, create_split_payload, parse_split_payload,
    generate_fingerprint, extract_from_audio, extract_from_video
)
from crypto import BitcoinStyleCrypto
from file_handler import normalize_path

# Configure page
st.set_page_config(
    page_title="CipherSteg | Advanced Multimedia Steganography",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00c6ff, #0072ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #8892b0;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #111927;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-success {
        background-color: #065f46;
        color: #34d399;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-warning {
        background-color: #78350f;
        color: #fbbf24;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown('<div class="main-header">🛡️ CipherSteg Universal Toolkit</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Multimedia Steganography • Bitcoin SECP256K1 Cryptography • Non-Linear PRNG Fingerprints • Reed-Solomon ECC</div>', unsafe_allow_html=True)

# Initialize Session State
if 'crypto' not in st.session_state:
    st.session_state.crypto = BitcoinStyleCrypto()

crypto = st.session_state.crypto

# Tabs Navigation
tabs = st.tabs([
    "🔑 Key Management",
    "📊 Capacity Analyzer",
    "🔒 Hide / Embed",
    "🔓 Extract Secret",
    "🧩 Merge Split Stego",
    "✍️ Sign & Verify"
])

# ==============================================================================
# TAB 1: KEY MANAGEMENT
# ==============================================================================
with tabs[0]:
    st.subheader("🔑 Bitcoin SECP256K1 Key Pair Generator")
    st.write("Generate or inspect Bitcoin-grade elliptic curve cryptographic keys for authenticated ECIES encryption.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Generate New Keypair")
        passphrase = st.text_input("Private Key Password (Optional)", type="password", help="Leave blank for unencrypted private key")
        
        if st.button("Generate SECP256K1 Keypair", type="primary"):
            priv_key, pub_key = crypto.generate_keypair()
            
            # Serialize
            temp_dir = tempfile.mkdtemp()
            priv_path = os.path.join(temp_dir, "my_private.pem")
            pub_path = os.path.join(temp_dir, "my_public.pem")
            
            crypto.save_private_key(priv_key, priv_path, password=passphrase if passphrase else None)
            crypto.save_public_key(pub_key, pub_path)
            
            with open(priv_path, "rb") as f:
                priv_bytes = f.read()
            with open(pub_path, "rb") as f:
                pub_bytes = f.read()
                
            fp = crypto.get_key_fingerprint(pub_key)
            
            st.success("New SECP256K1 Keypair generated successfully!")
            st.info(f"**Key Fingerprint (Double-SHA256):** `{fp}`")
            
            c_down1, c_down2 = st.columns(2)
            with c_down1:
                st.download_button(
                    label="📥 Download Private Key (.pem)",
                    data=priv_bytes,
                    file_name="my_private.pem",
                    mime="application/x-pem-file"
                )
            with c_down2:
                st.download_button(
                    label="📥 Download Public Key (.pem)",
                    data=pub_bytes,
                    file_name="my_public.pem",
                    mime="application/x-pem-file"
                )

    with col2:
        st.markdown("#### Inspect Existing Public Key")
        uploaded_pub = st.file_uploader("Upload Public Key (.pem)", type=["pem", "key"])
        if uploaded_pub:
            try:
                temp_pub = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                temp_pub.write(uploaded_pub.read())
                temp_pub.close()
                
                loaded_pub = crypto.load_public_key(temp_pub.name)
                fingerprint = crypto.get_key_fingerprint(loaded_pub)
                os.unlink(temp_pub.name)
                
                st.markdown(f"""
                <div class="metric-card">
                    <h4>Public Key Details</h4>
                    <p><b>Status:</b> <span class="badge-success">Valid SECP256K1</span></p>
                    <p><b>Fingerprint:</b> <code>{fingerprint}</code></p>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Invalid public key: {e}")

# ==============================================================================
# TAB 2: CAPACITY ANALYZER
# ==============================================================================
with tabs[1]:
    st.subheader("📊 Carrier Capacity & Feasibility Checker")
    st.write("Calculate how much hidden data a carrier file (image, audio, video, text) can hold.")

    c_cap1, c_cap2 = st.columns(2)
    
    with c_cap1:
        cap_cover = st.file_uploader("Choose Cover File (Image, Audio, Video, Text)", key="cap_cover")
    with c_cap2:
        cap_secret = st.file_uploader("Choose Target Secret File (Optional)", key="cap_secret")

    if cap_cover:
        t_cover = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(cap_cover.name)[1])
        t_cover.write(cap_cover.read())
        t_cover.close()

        file_type = detect_file_type(t_cover.name)
        capacity = get_file_capacity(t_cover.name)
        file_size = os.path.getsize(t_cover.name)

        st.markdown("---")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Cover File Type", file_type.upper())
        col_m2.metric("Cover File Size", f"{file_size / 1024:.2f} KB")
        col_m3.metric("Max Secret Capacity", f"{capacity / 1024:.2f} KB")

        if cap_secret:
            secret_size = cap_secret.size
            pct = (secret_size / capacity) * 100 if capacity > 0 else 999.0
            
            st.write(f"**Secret File Size:** `{secret_size / 1024:.2f} KB`")
            
            if secret_size <= capacity:
                st.progress(min(pct / 100.0, 1.0))
                st.success(f"✓ Feasible! Secret uses {pct:.1f}% of available carrier capacity.")
            else:
                parts_needed = (secret_size + capacity - 1) // capacity
                st.error(f"⚠️ Secret exceeds single carrier capacity ({pct:.1f}%).")
                st.warning(f"💡 Solution: Use the **Hide / Embed** tab with **Multi-carrier Split = {parts_needed} parts**.")

        os.unlink(t_cover.name)

# ==============================================================================
# TAB 3: HIDE / EMBED
# ==============================================================================
with tabs[2]:
    st.subheader("🔒 Conceal Secret in Multimedia Carrier")

    col_e1, col_e2 = st.columns([1, 1])

    with col_e1:
        st.markdown("#### 1. Select Files")
        embed_cover = st.file_uploader("Upload Carrier / Cover File", key="embed_cover")
        embed_secret = st.file_uploader("Upload Secret File to Conceal", key="embed_secret")

        if embed_cover:
            ext = os.path.splitext(embed_cover.name)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.webp']:
                st.image(embed_cover, caption=f"Cover Image: {embed_cover.name}", use_container_width=True)
            elif ext in ['.wav', '.mp3', '.flac']:
                st.audio(embed_cover)

    with col_e2:
        st.markdown("#### 2. Security & Embedding Options")
        
        use_encryption = st.checkbox("🔐 Encrypt with Recipient Public Key (SECP256K1 + AES-256-GCM)", value=True)
        recipient_file = None
        if use_encryption:
            recipient_file = st.file_uploader("Recipient Public Key (.pem)", type=["pem", "key"], key="recip_pub")
            if not recipient_file:
                st.info("Upload the recipient's public key to secure the payload.")

        enable_split = st.checkbox("🧩 Split payload across multiple carriers", value=False)
        split_parts = 2
        if enable_split:
            split_parts = st.number_input("Number of Carrier Parts", min_value=2, max_value=200, value=3)

        bit_pos = "lsb"
        if embed_cover and not embed_cover.name.lower().endswith(('.jpg', '.jpeg')):
            bit_pos = st.selectbox("Pixel Bit Depth (Lossless images only)", ["lsb", "mid", "msb"], index=0,
                                   help="LSB is imperceptible; Mid/MSB introduce visual distortions but resist certain compression.")

        st.markdown("---")
        btn_embed = st.button("🚀 Process & Embed Secret", type="primary", use_container_width=True)

    if btn_embed:
        if not embed_cover or not embed_secret:
            st.error("Please provide both a cover file and a secret file.")
        elif use_encryption and not recipient_file:
            st.error("Recipient public key is required when encryption is enabled.")
        else:
            with st.spinner("Embedding data with fingerprint scattering & error correction..."):
                try:
                    # Save temporary files
                    cover_ext = os.path.splitext(embed_cover.name)[1]
                    temp_cover = tempfile.NamedTemporaryFile(delete=False, suffix=cover_ext)
                    temp_cover.write(embed_cover.read())
                    temp_cover.close()

                    temp_secret = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(embed_secret.name)[1])
                    secret_bytes = embed_secret.read()
                    temp_secret.write(secret_bytes)
                    temp_secret.close()

                    # Generate Fingerprint Seed
                    import secrets
                    fingerprint_seed = secrets.token_hex(16)
                    fingerprint_bytes = generate_fingerprint(fingerprint_seed)

                    # Handle Encryption
                    final_secret_data = secret_bytes
                    encrypted_fp_bytes = None

                    if use_encryption:
                        temp_recip = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                        temp_recip.write(recipient_file.read())
                        temp_recip.close()
                        
                        recip_pub = crypto.load_public_key(temp_recip.name)
                        os.unlink(temp_recip.name)

                        final_secret_data = crypto.encrypt_file(secret_bytes, recip_pub)
                        encrypted_fp_bytes = crypto.encrypt_file(fingerprint_seed.encode(), recip_pub)

                    # Output file paths
                    temp_payload = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
                    temp_payload.write(final_secret_data)
                    temp_payload.close()

                    # Check Single vs Split
                    if not enable_split:
                        # Determine output extension
                        cov_type = detect_file_type(temp_cover.name)
                        if cov_type == 'image':
                            out_ext = '.jpg' if temp_cover.name.lower().endswith(('.jpg', '.jpeg')) else '.png'
                        elif cov_type == 'audio':
                            out_ext = '.flac'
                        elif cov_type == 'video':
                            out_ext = '.mp4'
                        else:
                            out_ext = cover_ext

                        temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=out_ext)
                        temp_out.close()

                        # Embed
                        embed_universal(temp_cover.name, temp_payload.name, temp_out.name, bit_position=bit_pos, fingerprint_bytes=fingerprint_bytes)

                        with open(temp_out.name, "rb") as f:
                            stego_bytes = f.read()

                        st.success("Embedding completed successfully!")

                        # Download buttons
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            st.download_button(
                                label=f"📥 Download Stego File ({out_ext})",
                                data=stego_bytes,
                                file_name=f"stego_output{out_ext}",
                                mime="application/octet-stream"
                            )
                        with col_d2:
                            if use_encryption:
                                st.download_button(
                                    label="🔑 Download Encrypted Fingerprint (.fingerprint.enc)",
                                    data=encrypted_fp_bytes,
                                    file_name=".fingerprint.enc",
                                    mime="application/octet-stream"
                                )
                            else:
                                st.download_button(
                                    label="🔑 Download Plain Fingerprint (.fingerprint)",
                                    data=fingerprint_seed.encode(),
                                    file_name=".fingerprint",
                                    mime="text/plain"
                                )

                        os.unlink(temp_out.name)
                    else:
                        # Split Embedding
                        parts = split_file(temp_payload.name, split_parts)
                        filename_bytes = embed_secret.name.encode('utf-8')
                        zip_buffer = io.BytesIO()

                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for idx, part_data in enumerate(parts):
                                payload = create_split_payload(part_data, idx, split_parts, filename_bytes, fingerprint_bytes)
                                temp_part_payload = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
                                temp_part_payload.write(payload)
                                temp_part_payload.close()

                                part_out = tempfile.NamedTemporaryFile(delete=False, suffix=cover_ext)
                                part_out.close()

                                embed_universal(temp_cover.name, temp_part_payload.name, part_out.name, fingerprint_bytes=fingerprint_bytes)

                                with open(part_out.name, "rb") as f:
                                    part_bytes = f.read()
                                
                                part_name = f"part_{idx+1}_{secrets.token_hex(8)}{cover_ext}"
                                zip_file.writestr(part_name, part_bytes)

                                os.unlink(temp_part_payload.name)
                                os.unlink(part_out.name)

                            if use_encryption:
                                zip_file.writestr(".fingerprint.enc", encrypted_fp_bytes)
                            else:
                                zip_file.writestr(".fingerprint", fingerprint_seed.encode())

                        st.success(f"Split and embedded across {split_parts} stego carrier parts!")
                        st.download_button(
                            label="📥 Download All Stego Parts & Fingerprint (.zip)",
                            data=zip_buffer.getvalue(),
                            file_name="stego_split_package.zip",
                            mime="application/zip"
                        )

                    # Cleanup
                    os.unlink(temp_cover.name)
                    os.unlink(temp_secret.name)
                    os.unlink(temp_payload.name)

                except Exception as e:
                    st.error(f"Embedding failed: {e}")

# ==============================================================================
# TAB 4: EXTRACT SECRET
# ==============================================================================
with tabs[3]:
    st.subheader("🔓 Extract Concealed Secret from Carrier")
    st.write("Extract and optionally decrypt payload from a single stego image, audio, video, or text carrier.")

    col_x1, col_x2 = st.columns(2)

    with col_x1:
        ext_stego = st.file_uploader("Upload Stego Carrier File", key="ext_stego")
        ext_fp = st.file_uploader("Upload Fingerprint File (.fingerprint or .fingerprint.enc)", key="ext_fp")

    with col_x2:
        do_decrypt = st.checkbox("Decrypt with SECP256K1 Private Key", value=True)
        priv_file = None
        priv_pwd = None
        if do_decrypt:
            priv_file = st.file_uploader("Upload Your Private Key (.pem)", type=["pem", "key"], key="ext_priv")
            priv_pwd = st.text_input("Private Key Password (if any)", type="password", key="ext_pwd")

        ext_bit_pos = st.selectbox("Pixel Bit Depth (Lossless images only)", ["lsb", "mid", "msb"], index=0, key="ext_bit_pos")

        btn_extract = st.button("🔍 Extract Secret", type="primary", use_container_width=True)

    if btn_extract:
        if not ext_stego or not ext_fp:
            st.error("Please provide both the stego carrier file and the fingerprint file.")
        elif do_decrypt and not priv_file:
            st.error("Private key is required to decrypt the payload.")
        else:
            with st.spinner("Extracting and reconstructing payload..."):
                try:
                    # Save temp stego
                    stego_ext = os.path.splitext(ext_stego.name)[1]
                    temp_stego = tempfile.NamedTemporaryFile(delete=False, suffix=stego_ext)
                    temp_stego.write(ext_stego.read())
                    temp_stego.close()

                    fp_bytes = ext_fp.read()
                    is_enc_fp = ext_fp.name.endswith(".enc")

                    # Handle Private Key
                    private_key = None
                    if is_enc_fp or do_decrypt:
                        temp_priv = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                        temp_priv.write(priv_file.read())
                        temp_priv.close()
                        private_key = crypto.load_private_key(temp_priv.name, password=priv_pwd if priv_pwd else None)
                        os.unlink(temp_priv.name)

                    # Get fingerprint seed
                    if is_enc_fp:
                        fingerprint_seed = crypto.decrypt_file(fp_bytes, private_key).decode()
                    else:
                        fingerprint_seed = fp_bytes.decode()

                    fingerprint_bytes = generate_fingerprint(fingerprint_seed)

                    out_dir = tempfile.mkdtemp()
                    extracted_path = extract_universal(temp_stego.name, output_folder=out_dir, bit_position=ext_bit_pos, fingerprint_bytes=fingerprint_bytes)

                    with open(extracted_path, "rb") as f:
                        recovered_data = f.read()

                    recovered_filename = os.path.basename(extracted_path)

                    if do_decrypt:
                        st.info("Decrypting with Bitcoin SECP256K1 + AES-GCM...")
                        recovered_data = crypto.decrypt_file(recovered_data, private_key)

                    st.success(f"✓ Successfully extracted: {recovered_filename} ({len(recovered_data):,} bytes)")

                    st.download_button(
                        label=f"📥 Download Recovered File: {recovered_filename}",
                        data=recovered_data,
                        file_name=recovered_filename,
                        mime="application/octet-stream"
                    )

                    os.unlink(temp_stego.name)
                    os.unlink(extracted_path)

                except Exception as e:
                    st.error(f"Extraction failed: {e}")

# ==============================================================================
# TAB 5: MERGE SPLIT STEGO
# ==============================================================================
with tabs[4]:
    st.subheader("🧩 Merge Split Stego Carrier Files")
    st.write("Upload all split carrier parts along with the fingerprint file to reassemble the original secret.")

    split_files = st.file_uploader("Upload All Split Stego Files", accept_multiple_files=True, key="merge_files")
    merge_fp = st.file_uploader("Upload Fingerprint File (.fingerprint or .fingerprint.enc)", key="merge_fp")

    m_decrypt = st.checkbox("Decrypt with Private Key", value=True, key="m_decrypt")
    m_priv = None
    m_pwd = None
    if m_decrypt:
        m_priv = st.file_uploader("Upload Recipient Private Key (.pem)", key="m_priv")
        m_pwd = st.text_input("Private Key Password", type="password", key="m_pwd")

    btn_merge = st.button("🔄 Reassemble & Recover File", type="primary")

    if btn_merge:
        if not split_files or not merge_fp:
            st.error("Please upload split stego files and the fingerprint file.")
        else:
            with st.spinner("Extracting and reassembling parts..."):
                try:
                    fp_bytes = merge_fp.read()
                    is_enc = merge_fp.name.endswith(".enc")

                    private_key = None
                    if is_enc or m_decrypt:
                        temp_p = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                        temp_p.write(m_priv.read())
                        temp_p.close()
                        private_key = crypto.load_private_key(temp_p.name, password=m_pwd if m_pwd else None)
                        os.unlink(temp_p.name)

                    if is_enc:
                        fp_seed = crypto.decrypt_file(fp_bytes, private_key).decode()
                    else:
                        fp_seed = fp_bytes.decode()

                    fp_bytes_calc = generate_fingerprint(fp_seed)

                    parts = {}
                    total_parts = None
                    orig_filename = None

                    for uploaded in split_files:
                        t_part = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1])
                        t_part.write(uploaded.read())
                        t_part.close()

                        file_type = detect_file_type(t_part.name)
                        if file_type == 'image':
                            payload = extract_universal(t_part.name, bit_position='lsb', fingerprint_bytes=fp_bytes_calc)
                        elif file_type == 'audio':
                            payload = extract_from_audio(t_part.name, fp_bytes_calc)
                        elif file_type == 'video':
                            payload = extract_from_video(t_part.name, fp_bytes_calc)
                        else:
                            os.unlink(t_part.name)
                            continue

                        os.unlink(t_part.name)
                        info = parse_split_payload(payload)

                        if total_parts is None:
                            total_parts = info['total_parts']
                            orig_filename = info['filename']

                        parts[info['part_num']] = info['data']

                    if len(parts) == 0:
                        st.error("No valid stego parts could be parsed.")
                    else:
                        st.write(f"Reassembled **{len(parts)} of {total_parts}** parts.")
                        merged_data = b''.join([parts[i] for i in sorted(parts.keys())])

                        if m_decrypt:
                            st.info("Decrypting merged payload...")
                            merged_data = crypto.decrypt_file(merged_data, private_key)

                        st.success(f"✓ File reconstructed: `{orig_filename}` ({len(merged_data):,} bytes)")
                        st.download_button(
                            label=f"📥 Download Reconstructed File: {orig_filename}",
                            data=merged_data,
                            file_name=orig_filename,
                            mime="application/octet-stream"
                        )

                except Exception as e:
                    st.error(f"Merge error: {e}")

# ==============================================================================
# TAB 6: SIGN & VERIFY
# ==============================================================================
with tabs[5]:
    st.subheader("✍️ Bitcoin ECDSA Digital Signatures")
    st.write("Cryptographically sign files and verify authenticity without tampering.")

    c_s1, c_s2 = st.columns(2)

    with c_s1:
        st.markdown("#### Sign a File")
        sign_file = st.file_uploader("Upload File to Sign", key="sign_file")
        sign_priv = st.file_uploader("Upload Private Key (.pem)", key="sign_priv")
        sign_pwd = st.text_input("Private Key Password (if applicable)", type="password", key="sign_pwd")

        if st.button("Create Digital Signature (.sig)", type="primary"):
            if not sign_file or not sign_priv:
                st.error("Upload both file and private key.")
            else:
                try:
                    t_priv = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                    t_priv.write(sign_priv.read())
                    t_priv.close()
                    
                    pk = crypto.load_private_key(t_priv.name, password=sign_pwd if sign_pwd else None)
                    os.unlink(t_priv.name)

                    sig_bytes = crypto.sign_data(sign_file.read(), pk)
                    st.success("File signed with SECP256K1 ECDSA!")
                    st.download_button(
                        label="📥 Download Signature (.sig)",
                        data=sig_bytes,
                        file_name=f"{sign_file.name}.sig",
                        mime="application/octet-stream"
                    )
                except Exception as e:
                    st.error(f"Signing failed: {e}")

    with c_s2:
        st.markdown("#### Verify Signature")
        ver_file = st.file_uploader("Upload Original File", key="ver_file")
        ver_sig = st.file_uploader("Upload Signature File (.sig)", key="ver_sig")
        ver_pub = st.file_uploader("Upload Signer's Public Key (.pem)", key="ver_pub")

        if st.button("Verify Signature"):
            if not ver_file or not ver_sig or not ver_pub:
                st.error("Please upload original file, signature, and public key.")
            else:
                try:
                    t_pub = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                    t_pub.write(ver_pub.read())
                    t_pub.close()

                    pub = crypto.load_public_key(t_pub.name)
                    os.unlink(t_pub.name)

                    is_valid = crypto.verify_signature(ver_file.read(), ver_sig.read(), pub)
                    if is_valid:
                        fp = crypto.get_key_fingerprint(pub)
                        st.markdown(f"""
                        <div class="metric-card">
                            <span class="badge-success">✓ VALID SIGNATURE</span>
                            <p style="margin-top: 8px;">The file is authentic and unaltered.</p>
                            <p><b>Signer Fingerprint:</b> <code>{fp}</code></p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error("❌ INVALID SIGNATURE: The file was modified or the wrong key was used.")
                except Exception as e:
                    st.error(f"Verification error: {e}")
