(() => {
  const qs = (id) => document.getElementById(id);
  const statusEl = qs('status');
  const logEl = qs('log');
  const connectBtn = qs('connect_btn');
  const disconnectBtn = qs('disconnect_btn');
  const callBtn = qs('call_btn');
  const hangupBtn = qs('hangup_btn');
  const muteBtn = qs('mute_btn');
  const dtmfBtn = qs('dtmf_btn');
  const dtmfDigits = qs('dtmf_digits');
  const targetInput = qs('target');
  
  // Dialer elements
  const dialerToggle = qs('dialer-toggle');
  const dialerDropdown = qs('dialer-dropdown');
  const clearBtn = qs('clear-btn');
  const callBtnDialer = qs('call-btn-dialer');
  
  const config = window.JSSIP_CONFIG || {};

  let ua = null;
  let session = null;
  let muted = false;
  let dialerVisible = false;

  const setStatus = (text) => {
    statusEl.textContent = text;
  };

  const log = (msg) => {
    const ts = new Date().toISOString();
    logEl.textContent += `[${ts}] ${msg}\n`;
    logEl.scrollTop = logEl.scrollHeight;
  };

  const setButtons = ({ connected, inCall }) => {
    connectBtn.disabled = connected;
    disconnectBtn.disabled = !connected;
    callBtn.disabled = !connected || inCall;
    hangupBtn.disabled = !inCall;
    muteBtn.disabled = !inCall;
    dtmfBtn.disabled = !inCall;
  };

  const resetSession = () => {
    session = null;
    muted = false;
    setButtons({ connected: !!ua && ua.isConnected(), inCall: false });
  };

  const connect = () => {
    const wsUri = (config.ws_uri || '').trim();
    const sipUri = (config.sip_uri || '').trim();
    const password = config.sip_password || '';
    const displayName = config.display_name || '';

    if (!wsUri || !sipUri || !password) {
      log('Missing SIP configuration. Ask admin to fill JsSIP settings in your profile.');
      alert('Missing SIP configuration.');
      return;
    }

    try {
      const socket = new JsSIP.WebSocketInterface(wsUri);
      const configuration = {
        sockets: [socket],
        uri: sipUri,
        password,
        display_name: displayName || undefined,
        session_timers: false,
      };
      ua = new JsSIP.UA(configuration);

      ua.on('connected', () => {
        setStatus('Connected');
        log('UA connected');
        setButtons({ connected: true, inCall: false });
      });
      ua.on('disconnected', () => {
        setStatus('Disconnected');
        log('UA disconnected');
        setButtons({ connected: false, inCall: false });
      });
      ua.on('registered', () => log('Registered'));
      ua.on('unregistered', () => log('Unregistered'));
      ua.on('registrationFailed', (e) => log(`Registration failed: ${e.cause}`));
      ua.on('newRTCSession', (e) => {
        if (session) {
          log('Another session incoming, rejecting');
          e.session.terminate();
          return;
        }
        session = e.session;
        attachSessionHandlers(session);
      });

      ua.start();
    } catch (err) {
      log(`Connect error: ${err}`);
    }
  };

  const disconnect = () => {
    if (session) {
      session.terminate();
    }
    if (ua) {
      ua.stop();
      ua = null;
    }
    setButtons({ connected: false, inCall: false });
    setStatus('Disconnected');
    log('UA stopped');
  };

  const call = () => {
    if (!ua || !ua.isConnected()) {
      alert('UA is not connected');
      return;
    }
    const target = qs('target').value.trim();
    if (!target) {
      alert('Enter target number or SIP URI');
      return;
    }
    const eventHandlers = {};
    const options = {
      mediaConstraints: { audio: true, video: false },
      pcConfig: {
        rtcpMuxPolicy: 'require',
        iceServers: [{ urls: ['stun:stun.l.google.com:19302'] }],
      },
    };
    session = ua.call(target, options, eventHandlers);
    attachSessionHandlers(session);
  };

  const attachSessionHandlers = (sess) => {
    setButtons({ connected: true, inCall: true });
    setStatus('Calling...');
    log(`Session state: ${sess.direction}`);

    sess.on('progress', () => {
      setStatus('Ringing...');
      log('Progress');
    });
    sess.on('accepted', () => {
      setStatus('In call');
      log('Call accepted');
    });
    sess.on('confirmed', () => log('Call confirmed'));
    sess.on('ended', (e) => {
      setStatus('Call ended');
      log(`Call ended: ${e && e.cause ? e.cause : 'normal'}`);
      resetSession();
    });
    sess.on('failed', (e) => {
      setStatus('Call failed');
      log(`Call failed: ${e && e.cause ? e.cause : 'unknown'}`);
      resetSession();
    });
    sess.on('peerconnection', (e) => {
      const pc = e.peerconnection;
      pc.ontrack = (event) => {
        const remoteStream = event.streams[0];
        const audio = new Audio();
        audio.srcObject = remoteStream;
        audio.play().catch(() => {
          log('Autoplay blocked, click to allow audio.');
        });
      };
    });
  };

  const hangup = () => {
    if (session) {
      session.terminate();
    }
  };

  const toggleMute = () => {
    if (!session) return;
    muted = !muted;
    session[muted ? 'mute' : 'unmute']({ audio: true });
    muteBtn.textContent = muted ? 'Unmute' : 'Mute';
    log(muted ? 'Muted microphone' : 'Unmuted microphone');
  };

  const sendDTMF = () => {
    if (!session) return;
    const digits = dtmfDigits.value.trim();
    if (!digits) return;
    session.sendDTMF(digits);
    log(`Sent DTMF: ${digits}`);
  };

  // Dialer functionality
  const toggleDialer = () => {
    dialerVisible = !dialerVisible;
    if (dialerVisible) {
      dialerDropdown.classList.add('show');
      dialerToggle.style.background = 'rgba(79,139,255,0.2)';
    } else {
      dialerDropdown.classList.remove('show');
      dialerToggle.style.background = 'rgba(255,255,255,0.1)';
    }
  };

  const addDigit = (digit) => {
    const targetField = qs('target');
    if (targetField) {
      const currentValue = targetField.value;
      targetField.value = currentValue + digit;
      targetField.focus();
      
      // Визуальная обратная связь
      const btn = document.querySelector(`[data-digit="${digit}"]`);
      if (btn) {
        btn.style.transform = 'translateY(0) scale(0.95)';
        setTimeout(() => {
          btn.style.transform = 'translateY(-2px) scale(1)';
        }, 100);
      }
    }
  };

  const clearNumber = () => {
    const targetField = qs('target');
    if (targetField) {
      targetField.value = '';
      targetField.focus();
    }
  };

  const makeCallFromDialer = () => {
    const targetField = qs('target');
    if (targetField && targetField.value.trim()) {
      toggleDialer(); // Закрыть диалер
      call(); // Использовать существующую функцию
    }
  };

  // Keyboard support
  const handleKeyboard = (e) => {
    const targetField = qs('target');
    
    // Цифры 0-9
    if (e.key >= '0' && e.key <= '9') {
      addDigit(e.key);
      e.preventDefault();
    }
    // Символы * и #
    else if (e.key === '*' || e.key === '#') {
      addDigit(e.key);
      e.preventDefault();
    }
    // Backspace для очистки
    else if (e.key === 'Backspace' && e.target !== targetField) {
      if (targetField && targetField.value.length > 0) {
        targetField.value = targetField.value.slice(0, -1);
        e.preventDefault();
      }
    }
    // Enter для звонка
    else if (e.key === 'Enter' && targetField && targetField.value.trim()) {
      call();
      e.preventDefault();
    }
    // Escape для закрытия диалера
    else if (e.key === 'Escape' && dialerVisible) {
      toggleDialer();
      e.preventDefault();
    }
  };

  // Закрытие диалера при клике вне его
  const handleOutsideClick = (e) => {
    if (dialerVisible && dialerDropdown && dialerToggle && 
        !dialerDropdown.contains(e.target) && !dialerToggle.contains(e.target)) {
      toggleDialer();
    }
  };

  connectBtn.addEventListener('click', connect);
  disconnectBtn.addEventListener('click', disconnect);
  callBtn.addEventListener('click', call);
  hangupBtn.addEventListener('click', hangup);
  muteBtn.addEventListener('click', toggleMute);
  dtmfBtn.addEventListener('click', sendDTMF);

  // Dialer event listeners
  if (dialerToggle) dialerToggle.addEventListener('click', toggleDialer);
  if (clearBtn) clearBtn.addEventListener('click', clearNumber);
  if (callBtnDialer) callBtnDialer.addEventListener('click', makeCallFromDialer);

  // Keypad buttons
  document.querySelectorAll('.keypad-btn[data-digit]').forEach(btn => {
    btn.addEventListener('click', () => {
      const digit = btn.getAttribute('data-digit');
      addDigit(digit);
    });
  });

  // Global keyboard and click listeners
  document.addEventListener('keydown', handleKeyboard);
  document.addEventListener('click', handleOutsideClick);

  setButtons({ connected: false, inCall: false });
  setStatus('Disconnected');

  // Initialize with enhanced dialer info
  log('JsSIP client loaded with enhanced dialer!');
  log('📱 Click phone icon to open keypad');
  log('⌨️ Keyboard shortcuts: 0-9, *, #, Enter=Call, Esc=Close dialer');
  log('🔗 Click "Connect" to start SIP connection');

  // auto-connect if config is complete
  if (config.ws_uri && config.sip_uri && config.sip_password) {
    connect();
  }
})();
