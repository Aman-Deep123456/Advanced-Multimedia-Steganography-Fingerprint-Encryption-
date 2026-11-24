// CIPHERSTEG UNIVERSAL CLIENT ENGINE

document.addEventListener('DOMContentLoaded', () => {
  // 1. Navigation Tabs
  const navBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      
      navBtns.forEach(b => {
        b.classList.remove('active', 'bg-cyan-500/10', 'text-cyan-400', 'border-cyan-500/30', 'font-semibold');
        b.classList.add('text-gray-400', 'border-transparent');
      });
      btn.classList.add('active', 'bg-cyan-500/10', 'text-cyan-400', 'border-cyan-500/30', 'font-semibold');
      btn.classList.remove('text-gray-400', 'border-transparent');

      tabContents.forEach(content => {
        if (content.id === targetId) {
          content.classList.remove('hidden');
        } else {
          content.classList.add('hidden');
        }
      });
      lucide.createIcons();
    });
  });

  // 2. Logging utility
  const terminal = document.getElementById('terminal-logs');
  function log(message, type = 'info') {
    const time = new Date().toLocaleTimeString();
    const p = document.createElement('p');
    let color = 'text-gray-300';
    let icon = '❯';

    if (type === 'success') {
      color = 'text-emerald-400 font-semibold';
      icon = '✓';
    } else if (type === 'warning') {
      color = 'text-amber-400';
      icon = '⚠';
    } else if (type === 'error') {
      color = 'text-rose-400 font-bold';
      icon = '✗';
    } else if (type === 'crypto') {
      color = 'text-cyan-400 font-mono';
      icon = '⚡';
    }

    p.className = `${color} leading-relaxed text-xs break-all`;
    p.innerHTML = `<span class="text-gray-500">[${time}]</span> ${icon} ${message}`;
    terminal.appendChild(p);
    terminal.scrollTop = terminal.scrollHeight;
  }

  document.getElementById('btn-clear-logs').addEventListener('click', () => {
    terminal.innerHTML = '<p class="text-gray-500">[SYSTEM] Logs cleared.</p>';
  });

  // Toast Notification
  function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const border = type === 'error' ? 'border-rose-500' : (type === 'success' ? 'border-emerald-500' : 'border-cyan-500');
    toast.className = `p-4 rounded-xl glass-panel border ${border} text-white shadow-2xl max-w-sm pointer-events-auto transition-all duration-300 transform translate-y-2 opacity-0 flex items-start space-x-3`;
    
    let icon = type === 'error' ? 'alert-triangle' : (type === 'success' ? 'check-circle' : 'info');
    toast.innerHTML = `
      <div class="mt-0.5"><i data-lucide="${icon}" class="w-5 h-5 text-cyan-400"></i></div>
      <div class="flex-1">
        <p class="font-bold text-xs uppercase tracking-wide">${title}</p>
        <p class="text-xs text-gray-300 mt-0.5">${message}</p>
      </div>
    `;
    container.appendChild(toast);
    lucide.createIcons();

    setTimeout(() => {
      toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    setTimeout(() => {
      toast.classList.add('opacity-0', 'translate-y-2');
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  // 3. Fetch System Info
  fetch('/api/system_info')
    .then(res => res.json())
    .then(data => {
      const badge = document.getElementById('device-badge');
      if (badge && data.device) {
        badge.textContent = `${data.device.toUpperCase()} ACCELERATED`;
      }
      log(`Kernel connected: Device ${data.device}, SECP256K1 Bitcoin curves active.`, 'crypto');
    })
    .catch(err => {
      log('Could not load hardware device stats: ' + err, 'warning');
    });

  // 4. File Helper & Dropzone Binder
  function setupDropzone(dropzoneId, inputId, onFileSelected) {
    const dropzone = document.getElementById(dropzoneId);
    const input = document.getElementById(inputId);

    if (!dropzone || !input) return;

    dropzone.addEventListener('click', (e) => {
      if (e.target.tagName !== 'BUTTON' && !e.target.closest('button')) {
        input.click();
      }
    });

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        input.files = e.dataTransfer.files;
        onFileSelected(input.files);
      }
    });

    input.addEventListener('change', () => {
      if (input.files.length > 0) {
        onFileSelected(input.files);
      }
    });
  }

  function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  // ===========================================================================
  // EMBED TAB WORKFLOW & REALTIME CAPACITY
  // ===========================================================================
  let currentCarrierFile = null;
  let currentSecretFile = null;
  let currentRecipientKeyFile = null;

  setupDropzone('dropzone-carrier', 'input-carrier', (files) => {
    currentCarrierFile = files[0];
    document.getElementById('carrier-empty-view').classList.add('hidden');
    document.getElementById('carrier-loaded-view').classList.remove('hidden');
    document.getElementById('carrier-name').textContent = currentCarrierFile.name;
    document.getElementById('carrier-size').textContent = formatBytes(currentCarrierFile.size);
    document.getElementById('carrier-ext-badge').textContent = currentCarrierFile.name.split('.').pop().toUpperCase();

    // Preview if image
    const previewContainer = document.getElementById('carrier-preview-container');
    previewContainer.innerHTML = '';
    if (currentCarrierFile.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(currentCarrierFile);
      img.className = 'max-h-44 object-contain rounded';
      previewContainer.appendChild(img);
    } else if (currentCarrierFile.type.startsWith('audio/')) {
      const audio = document.createElement('audio');
      audio.controls = true;
      audio.src = URL.createObjectURL(currentCarrierFile);
      audio.className = 'w-full px-4';
      previewContainer.appendChild(audio);
    }

    log(`Carrier selected: ${currentCarrierFile.name} (${formatBytes(currentCarrierFile.size)})`, 'info');
    evaluateCapacity();
  });

  document.getElementById('btn-remove-carrier').addEventListener('click', (e) => {
    e.stopPropagation();
    currentCarrierFile = null;
    document.getElementById('input-carrier').value = '';
    document.getElementById('carrier-empty-view').classList.remove('hidden');
    document.getElementById('carrier-loaded-view').classList.add('hidden');
    document.getElementById('carrier-preview-container').innerHTML = '';
    hideCapacityMeter();
  });

  setupDropzone('dropzone-secret', 'input-secret', (files) => {
    currentSecretFile = files[0];
    document.getElementById('secret-empty-view').classList.add('hidden');
    document.getElementById('secret-loaded-view').classList.remove('hidden');
    document.getElementById('secret-name').textContent = currentSecretFile.name;
    document.getElementById('secret-size').textContent = formatBytes(currentSecretFile.size);
    document.getElementById('secret-ext-badge').textContent = currentSecretFile.name.split('.').pop().toUpperCase();

    log(`Secret loaded: ${currentSecretFile.name} (${formatBytes(currentSecretFile.size)})`, 'info');
    evaluateCapacity();
  });

  document.getElementById('btn-remove-secret').addEventListener('click', (e) => {
    e.stopPropagation();
    currentSecretFile = null;
    document.getElementById('input-secret').value = '';
    document.getElementById('secret-empty-view').classList.remove('hidden');
    document.getElementById('secret-loaded-view').classList.add('hidden');
    evaluateCapacity();
  });

  function evaluateCapacity() {
    if (!currentCarrierFile) {
      hideCapacityMeter();
      return;
    }

    const formData = new FormData();
    formData.append('cover', currentCarrierFile);
    if (currentSecretFile) {
      formData.append('secret', currentSecretFile);
    }

    fetch('/api/capacity', {
      method: 'POST',
      body: formData
    })
    .then(res => res.json())
    .then(data => {
      if (!data.success) return;

      const meterBox = document.getElementById('capacity-meter-box');
      meterBox.classList.remove('hidden');

      const progressBar = document.getElementById('capacity-progress-bar');
      const percentBadge = document.getElementById('capacity-percent-badge');
      const secretLabel = document.getElementById('capacity-secret-label');
      const coverLabel = document.getElementById('capacity-cover-label');
      const alertBox = document.getElementById('capacity-alert-box');

      coverLabel.textContent = `Carrier Usable Limit: ${formatBytes(data.capacity)}`;

      if (currentSecretFile) {
        secretLabel.textContent = `Secret: ${formatBytes(data.secret_size)}`;
        percentBadge.textContent = `${data.pct}% USED`;

        const fillWidth = Math.min(data.pct, 100);
        progressBar.style.width = `${fillWidth}%`;

        if (data.fit) {
          progressBar.className = 'bg-gradient-to-r from-emerald-500 to-cyan-500 h-full rounded-full transition-all duration-500';
          percentBadge.className = 'px-2 py-0.5 rounded text-xs font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800';
          alertBox.className = 'mt-3 text-xs font-medium p-3 rounded-xl bg-emerald-950/60 border border-emerald-800 text-emerald-300';
          alertBox.innerHTML = `✓ Feasible: Payload will easily fit inside carrier.`;
          alertBox.classList.remove('hidden');
        } else {
          progressBar.className = 'bg-gradient-to-r from-amber-500 to-rose-500 h-full rounded-full transition-all duration-500';
          percentBadge.className = 'px-2 py-0.5 rounded text-xs font-mono font-bold bg-rose-950 text-rose-400 border border-rose-800';
          alertBox.className = 'mt-3 text-xs font-medium p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300';
          alertBox.innerHTML = `⚠ Exceeds Single Carrier Capacity (${data.pct}%). Recommended: Check <b>Multi-Carrier Splitting</b> and set parts to <b>${data.split_needed}</b>.`;
          alertBox.classList.remove('hidden');

          // Auto-suggest split slider
          const splitCheck = document.getElementById('check-split');
          const splitSlider = document.getElementById('input-split-slider');
          if (!splitCheck.checked) {
            splitSlider.value = data.split_needed;
            document.getElementById('split-parts-label').textContent = `${data.split_needed} Parts`;
          }
        }
      } else {
        secretLabel.textContent = 'Secret: Not selected';
        percentBadge.textContent = 'CAPACITY READY';
        progressBar.style.width = '0%';
        alertBox.classList.add('hidden');
      }
    });
  }

  function hideCapacityMeter() {
    document.getElementById('capacity-meter-box').classList.add('hidden');
  }

  // Recipient Key Selection
  const btnBrowseRecipient = document.getElementById('btn-browse-recipient');
  const inputRecipientKey = document.getElementById('input-recipient-key');
  btnBrowseRecipient.addEventListener('click', () => inputRecipientKey.click());
  inputRecipientKey.addEventListener('change', () => {
    if (inputRecipientKey.files.length > 0) {
      currentRecipientKeyFile = inputRecipientKey.files[0];
      document.getElementById('recipient-key-name').textContent = currentRecipientKeyFile.name;
      log(`Recipient public key loaded: ${currentRecipientKeyFile.name}`, 'crypto');
    }
  });

  // Split Checkbox & Slider
  const checkSplit = document.getElementById('check-split');
  const splitSliderSection = document.getElementById('split-slider-section');
  const splitSlider = document.getElementById('input-split-slider');
  const splitPartsLabel = document.getElementById('split-parts-label');

  checkSplit.addEventListener('change', () => {
    if (checkSplit.checked) {
      splitSliderSection.classList.remove('opacity-50', 'pointer-events-none');
    } else {
      splitSliderSection.classList.add('opacity-50', 'pointer-events-none');
    }
  });

  splitSlider.addEventListener('input', () => {
    splitPartsLabel.textContent = `${splitSlider.value} Parts`;
  });

  // EXECUTE EMBED
  const btnExecuteEmbed = document.getElementById('btn-execute-embed');
  btnExecuteEmbed.addEventListener('click', () => {
    if (!currentCarrierFile) {
      showToast('Missing Carrier', 'Please choose a carrier file first.', 'error');
      return;
    }
    if (!currentSecretFile) {
      showToast('Missing Secret', 'Please select a secret file to hide.', 'error');
      return;
    }

    const encrypt = document.getElementById('check-encrypt').checked;
    if (encrypt && !currentRecipientKeyFile) {
      showToast('Missing Key', 'Recipient public key is required when encryption is enabled.', 'error');
      return;
    }

    btnExecuteEmbed.disabled = true;
    btnExecuteEmbed.innerHTML = `<span class="animate-spin inline-block mr-2">⚙</span> Concealing Secret & Applying Reed-Solomon ECC...`;
    log('Beginning embedding pipeline...', 'crypto');

    const formData = new FormData();
    formData.append('cover', currentCarrierFile);
    formData.append('secret', currentSecretFile);
    formData.append('encrypt', encrypt ? 'true' : 'false');
    if (encrypt && currentRecipientKeyFile) {
      formData.append('recipient_key', currentRecipientKeyFile);
    }
    formData.append('split', checkSplit.checked ? splitSlider.value : '1');
    formData.append('bit_position', document.getElementById('select-bit-pos').value);

    fetch('/api/embed', {
      method: 'POST',
      body: formData
    })
    .then(res => res.json())
    .then(data => {
      btnExecuteEmbed.disabled = false;
      btnExecuteEmbed.innerHTML = `<i data-lucide="zap" class="w-5 h-5 fill-current"></i><span>Execute Steganographic Concealment</span>`;
      lucide.createIcons();

      if (!data.success) {
        showToast('Embedding Failed', data.error, 'error');
        log('Embedding failed: ' + data.error, 'error');
        return;
      }

      if (data.logs) {
        data.logs.forEach(l => log(l, 'info'));
      }
      log('✓ Steganography concealment completed successfully!', 'success');
      showToast('Success', 'Stego file and fingerprint generated!', 'success');

      // Populate download results
      const resultCard = document.getElementById('embed-result-card');
      const actionArea = document.getElementById('embed-download-actions');
      const fpTag = document.getElementById('result-fp-tag');
      actionArea.innerHTML = '';

      fpTag.textContent = `FP: ${data.fingerprint_seed.slice(0, 16)}...`;

      if (data.downloads.is_split) {
        actionArea.innerHTML = `
          <a href="${data.downloads.archive}" download class="col-span-2 py-3 px-4 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-400 hover:to-indigo-500 text-white font-bold text-center text-xs tracking-wider uppercase transition shadow-lg shadow-purple-500/25">
            📥 Download Split Stego Archive (.zip - ${data.downloads.parts_count} parts)
          </a>
        `;
      } else {
        actionArea.innerHTML = `
          <a href="${data.downloads.stego}" download class="py-3 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-bold text-center text-xs tracking-wider uppercase transition shadow-lg shadow-cyan-500/25">
            📥 Download Stego Carrier (${data.downloads.stego_name})
          </a>
          <a href="${data.downloads.fingerprint}" download class="py-3 px-4 rounded-xl bg-cyber-850 hover:bg-cyber-800 border border-white/10 text-cyan-400 font-bold text-center text-xs tracking-wider uppercase transition">
            🔑 Download Fingerprint (${data.downloads.fingerprint_name})
          </a>
        `;
      }

      resultCard.classList.remove('hidden');
      resultCard.scrollIntoView({ behavior: 'smooth' });
    })
    .catch(err => {
      btnExecuteEmbed.disabled = false;
      btnExecuteEmbed.innerHTML = `<i data-lucide="zap" class="w-5 h-5 fill-current"></i><span>Execute Steganographic Concealment</span>`;
      lucide.createIcons();
      showToast('Error', err.message, 'error');
      log('Error during embed: ' + err.message, 'error');
    });
  });

  // ===========================================================================
  // EXTRACT TAB WORKFLOW
  // ===========================================================================
  let currentExtStegoFile = null;
  let currentExtFpFile = null;
  let currentExtPrivKeyFile = null;

  setupDropzone('dropzone-ext-stego', 'input-ext-stego', (files) => {
    currentExtStegoFile = files[0];
    document.getElementById('ext-stego-empty').classList.add('hidden');
    document.getElementById('ext-stego-loaded').classList.remove('hidden');
    document.getElementById('ext-stego-name').textContent = currentExtStegoFile.name;
    document.getElementById('ext-stego-size').textContent = formatBytes(currentExtStegoFile.size);
    log(`Stego carrier loaded for extraction: ${currentExtStegoFile.name}`, 'info');
  });

  setupDropzone('dropzone-ext-fp', 'input-ext-fp', (files) => {
    currentExtFpFile = files[0];
    document.getElementById('ext-fp-empty').classList.add('hidden');
    document.getElementById('ext-fp-loaded').classList.remove('hidden');
    document.getElementById('ext-fp-name').textContent = currentExtFpFile.name;
    document.getElementById('ext-fp-type').textContent = currentExtFpFile.name.endsWith('.enc') ? 'ENCRYPTED TOKEN' : 'PLAIN SEED';
    log(`Fingerprint loaded: ${currentExtFpFile.name}`, 'crypto');
  });

  const btnBrowseExtPriv = document.getElementById('btn-browse-ext-priv');
  const inputExtPriv = document.getElementById('input-ext-privkey');
  btnBrowseExtPriv.addEventListener('click', () => inputExtPriv.click());
  inputExtPriv.addEventListener('change', () => {
    if (inputExtPriv.files.length > 0) {
      currentExtPrivKeyFile = inputExtPriv.files[0];
      document.getElementById('ext-priv-name').textContent = currentExtPrivKeyFile.name;
      log(`Private key loaded: ${currentExtPrivKeyFile.name}`, 'crypto');
    }
  });

  const btnExecuteExtract = document.getElementById('btn-execute-extract');
  btnExecuteExtract.addEventListener('click', () => {
    if (!currentExtStegoFile || !currentExtFpFile) {
      showToast('Missing Inputs', 'Provide both Stego Carrier and Fingerprint token.', 'error');
      return;
    }

    const decrypt = document.getElementById('check-ext-decrypt').checked;
    if (decrypt && !currentExtPrivKeyFile) {
      showToast('Private Key Required', 'Upload your private key to decrypt payload.', 'error');
      return;
    }

    btnExecuteExtract.disabled = true;
    btnExecuteExtract.innerHTML = `<span class="animate-spin inline-block mr-2">⚙</span> Extracting PRNG Positions & Decoding ECC...`;

    const formData = new FormData();
    formData.append('stego', currentExtStegoFile);
    formData.append('fingerprint', currentExtFpFile);
    formData.append('decrypt', decrypt ? 'true' : 'false');
    if (decrypt && currentExtPrivKeyFile) {
      formData.append('private_key', currentExtPrivKeyFile);
    }
    formData.append('password', document.getElementById('input-ext-pwd').value);

    fetch('/api/extract', {
      method: 'POST',
      body: formData
    })
    .then(res => res.json())
    .then(data => {
      btnExecuteExtract.disabled = false;
      btnExecuteExtract.innerHTML = `<i data-lucide="download-cloud" class="w-5 h-5"></i><span>Extract & Reconstruct Secret File</span>`;
      lucide.createIcons();

      if (!data.success) {
        showToast('Extraction Failed', data.error, 'error');
        log('Extraction error: ' + data.error, 'error');
        return;
      }

      if (data.logs) {
        data.logs.forEach(l => log(l, 'info'));
      }
      log(`✓ Payload recovered: ${data.filename} (${formatBytes(data.size)})`, 'success');
      showToast('Extracted!', `Recovered ${data.filename}`, 'success');

      document.getElementById('recovered-filename').textContent = data.filename;
      document.getElementById('recovered-filesize').textContent = `Size: ${formatBytes(data.size)}`;
      const downloadBtn = document.getElementById('btn-download-recovered');
      downloadBtn.href = data.download_url;
      downloadBtn.setAttribute('download', data.filename);

      document.getElementById('extract-result-card').classList.remove('hidden');
    })
    .catch(err => {
      btnExecuteExtract.disabled = false;
      btnExecuteExtract.innerHTML = `<i data-lucide="download-cloud" class="w-5 h-5"></i><span>Extract & Reconstruct Secret File</span>`;
      lucide.createIcons();
      showToast('Error', err.message, 'error');
      log('Extract error: ' + err.message, 'error');
    });
  });

  // ===========================================================================
  // CAPACITY LAB TAB
  // ===========================================================================
  let capCover = null;
  let capSecret = null;

  setupDropzone('dropzone-cap-cover', 'input-cap-cover', (files) => {
    capCover = files[0];
    document.getElementById('cap-cover-selected').textContent = `${capCover.name} (${formatBytes(capCover.size)})`;
    analyzeCapacityLab();
  });

  setupDropzone('dropzone-cap-secret', 'input-cap-secret', (files) => {
    capSecret = files[0];
    document.getElementById('cap-secret-selected').textContent = `${capSecret.name} (${formatBytes(capSecret.size)})`;
    analyzeCapacityLab();
  });

  function analyzeCapacityLab() {
    if (!capCover) return;
    const formData = new FormData();
    formData.append('cover', capCover);
    if (capSecret) formData.append('secret', capSecret);

    fetch('/api/capacity', { method: 'POST', body: formData })
      .then(res => res.json())
      .then(data => {
        if (!data.success) return;
        document.getElementById('capacity-details-grid').classList.remove('hidden');
        document.getElementById('metric-carrier-type').textContent = data.cover_type;
        document.getElementById('metric-carrier-size').textContent = formatBytes(data.cover_size);
        document.getElementById('metric-carrier-capacity').textContent = formatBytes(data.capacity);
        log(`Capacity Lab: ${data.cover_type} has usable capacity of ${formatBytes(data.capacity)}`, 'info');
      });
  }

  // ===========================================================================
  // KEY VAULT TAB
  // ===========================================================================
  let lastPrivPem = '';
  let lastPubPem = '';

  document.getElementById('btn-generate-keys').addEventListener('click', () => {
    const pwd = document.getElementById('input-keygen-pwd').value;
    log('Generating SECP256K1 Bitcoin Keypair with PKCS8 encoding...', 'crypto');

    fetch('/api/keygen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pwd })
    })
    .then(res => res.json())
    .then(data => {
      if (!data.success) {
        showToast('Keygen Error', data.error, 'error');
        return;
      }
      lastPrivPem = data.private_key;
      lastPubPem = data.public_key;

      document.getElementById('generated-fingerprint').textContent = data.fingerprint;
      document.getElementById('keygen-results').classList.remove('hidden');
      log(`Keypair created. Bitcoin double-SHA256 fingerprint: ${data.fingerprint}`, 'success');
      showToast('Keypair Generated', 'SECP256K1 keys ready to download.', 'success');
    });
  });

  function downloadText(text, filename) {
    const blob = new Blob([text], { type: 'application/x-pem-file' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  document.getElementById('btn-dl-priv').addEventListener('click', () => {
    if (lastPrivPem) downloadText(lastPrivPem, 'my_private.pem');
  });
  document.getElementById('btn-dl-pub').addEventListener('click', () => {
    if (lastPubPem) downloadText(lastPubPem, 'my_public.pem');
  });

  // ===========================================================================
  // SIGN & VERIFY TAB
  // ===========================================================================
  document.getElementById('btn-execute-sign').addEventListener('click', () => {
    const file = document.getElementById('input-sign-file').files[0];
    const priv = document.getElementById('input-sign-priv').files[0];
    if (!file || !priv) {
      showToast('Missing input', 'Select file and private key to sign.', 'error');
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('private_key', priv);

    fetch('/api/sign', { method: 'POST', body: formData })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          const btn = document.getElementById('btn-download-sig');
          btn.href = data.download_url;
          btn.setAttribute('download', data.sig_name);
          btn.classList.remove('hidden');
          showToast('Signed', 'ECDSA signature generated.', 'success');
          log(`File signed via SECP256K1 ECDSA: ${data.sig_name}`, 'success');
        } else {
          showToast('Error', data.error, 'error');
        }
      });
  });

  document.getElementById('btn-execute-verify').addEventListener('click', () => {
    const file = document.getElementById('input-verify-file').files[0];
    const sig = document.getElementById('input-verify-sig').files[0];
    const pub = document.getElementById('input-verify-pub').files[0];

    if (!file || !sig || !pub) {
      showToast('Missing input', 'Provide file, signature, and public key.', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('signature', sig);
    formData.append('public_key', pub);

    fetch('/api/verify', { method: 'POST', body: formData })
      .then(res => res.json())
      .then(data => {
        const badge = document.getElementById('verify-result-badge');
        badge.classList.remove('hidden');
        if (data.valid) {
          badge.className = 'p-3 rounded-xl text-center text-xs font-bold bg-emerald-950 border border-emerald-500 text-emerald-400';
          badge.innerHTML = `✓ VALID SIGNATURE — Authentic file from key ${data.fingerprint}`;
          log(`Signature validated successfully for key ${data.fingerprint}`, 'success');
        } else {
          badge.className = 'p-3 rounded-xl text-center text-xs font-bold bg-rose-950 border border-rose-500 text-rose-400';
          badge.innerHTML = `✗ INVALID SIGNATURE — Content modified or wrong key.`;
          log('Signature verification failed.', 'error');
        }
      });
  });
});
