/**
 * Modern SIP Client - WebRTC/SIPml Integration
 * ES6+ module for handling SIP calls with proper state management
 */

class ModernSipClient {
    constructor(config = {}) {
        this.config = {
            websocket_uri: config.websocket_uri || '',
            sip_domain: config.sip_domain || '',
            sip_username: config.sip_username || '',
            display_name: config.display_name || '',
            password: config.password || '',
            ...config
        };

        this.state = {
            registered: false,
            calling: false,
            inCall: false,
            muted: false,
            speakerOn: false,
            callStartTime: null,
            currentNumber: '',
            connectionStatus: 'disconnected'
        };

        this.sipStack = null;
        this.sipSession = null;
        this.callTimer = null;
        this.audioContext = null;
        this.mediaStream = null;

        this.elements = {};
        this.eventListeners = new Map();

        this.init();
    }

    init() {
        this.bindElements();
        this.attachEventListeners();
        this.initializeSipStack();
        this.startConnectionMonitoring();
    }

    bindElements() {
        this.elements = {
            statusIndicator: document.querySelector('.status-indicator'),
            connectionStatus: document.querySelector('.connection-status span'),
            numberInput: document.querySelector('.number-input'),
            callNumber: document.querySelector('.call-number'),
            callStatus: document.querySelector('.call-status'),
            callDuration: document.querySelector('.call-duration'),
            audioVisualizer: document.querySelector('.audio-visualizer'),
            
            // Buttons
            btnCall: document.querySelector('.btn-call'),
            btnMute: document.querySelector('[data-action="mute"]'),
            btnSpeaker: document.querySelector('[data-action="speaker"]'),
            btnTransfer: document.querySelector('[data-action="transfer"]'),
            btnKeypad: document.querySelector('[data-action="keypad"]'),
            btnSettings: document.querySelector('[data-action="settings"]'),
            
            // Keypad
            keypadKeys: document.querySelectorAll('.key'),
            
            // Settings
            settingsPanel: document.querySelector('.settings-panel'),
            settingsForm: document.querySelector('.settings-form'),
            btnCloseSettings: document.querySelector('.btn-close')
        };
    }

    attachEventListeners() {
        // Call button
        this.elements.btnCall?.addEventListener('click', () => this.handleCallAction());

        // Keypad
        this.elements.keypadKeys.forEach(key => {
            key.addEventListener('click', (e) => {
                const digit = e.currentTarget.dataset.digit;
                this.handleKeypadPress(digit);
            });
        });

        // Number input
        this.elements.numberInput?.addEventListener('input', (e) => {
            this.state.currentNumber = e.target.value;
            this.updateCallButton();
        });

        this.elements.numberInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && this.canMakeCall()) {
                this.handleCallAction();
            }
        });

        // Action buttons
        this.elements.btnMute?.addEventListener('click', () => this.toggleMute());
        this.elements.btnSpeaker?.addEventListener('click', () => this.toggleSpeaker());
        this.elements.btnTransfer?.addEventListener('click', () => this.showTransferDialog());
        this.elements.btnKeypad?.addEventListener('click', () => this.toggleDTMF());
        this.elements.btnSettings?.addEventListener('click', () => this.showSettings());

        // Settings
        this.elements.btnCloseSettings?.addEventListener('click', () => this.hideSettings());
        this.elements.settingsPanel?.addEventListener('click', (e) => {
            if (e.target === this.elements.settingsPanel) {
                this.hideSettings();
            }
        });

        this.elements.settingsForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveSettings();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }

    initializeSipStack() {
        if (!window.SIPml) {
            this.showNotification('SIPml library not loaded', 'error');
            return;
        }

        try {
            // Initialize SIPml stack
            SIPml.init(() => {
                this.createSipStack();
            }, (error) => {
                console.error('SIPml initialization failed:', error);
                this.updateConnectionStatus('error');
                this.showNotification('Failed to initialize SIP client', 'error');
            });
        } catch (error) {
            console.error('SIPml setup error:', error);
            this.updateConnectionStatus('error');
        }
    }

    createSipStack() {
        if (!this.config.websocket_uri || !this.config.sip_domain) {
            this.updateConnectionStatus('configuration_missing');
            this.showNotification('SIP configuration missing. Please check settings.', 'warning');
            return;
        }

        this.sipStack = new SIPml.Stack({
            realm: this.config.sip_domain,
            impi: this.config.sip_username,
            impu: `sip:${this.config.sip_username}@${this.config.sip_domain}`,
            password: this.config.password,
            display_name: this.config.display_name,
            websocket_proxy_url: this.config.websocket_uri,
            outbound_proxy_url: this.config.websocket_uri,
            ice_servers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ],
            enable_rtcweb_breaker: true,
            events_listener: {
                events: '*',
                listener: (e) => this.handleSipStackEvent(e)
            }
        });

        this.sipStack.start();
    }

    handleSipStackEvent(event) {
        console.log('SIP Stack Event:', event.type, event);

        switch (event.type) {
            case 'started':
                this.updateConnectionStatus('connecting');
                this.showNotification('Connecting to SIP server...', 'info');
                break;

            case 'stopped':
                this.updateConnectionStatus('disconnected');
                this.state.registered = false;
                break;

            case 'failed_to_start':
                this.updateConnectionStatus('error');
                this.showNotification('Failed to start SIP client', 'error');
                break;

            case 'i_new_call':
                this.handleIncomingCall(event.newSession);
                break;

            case 'm_permission_requested':
                this.showNotification('Microphone permission requested', 'info');
                break;

            case 'm_permission_accepted':
                this.showNotification('Microphone access granted', 'success');
                break;

            case 'm_permission_refused':
                this.showNotification('Microphone access denied', 'error');
                break;

            default:
                if (event.type.includes('register')) {
                    this.handleRegistrationEvent(event);
                }
                break;
        }
    }

    handleRegistrationEvent(event) {
        switch (event.type) {
            case 'i_ao_request':
                this.updateConnectionStatus('registering');
                break;

            case 'i_new_message':
                if (event.getSipResponseCode() === 200) {
                    this.state.registered = true;
                    this.updateConnectionStatus('connected');
                    this.showNotification('Successfully registered', 'success');
                } else {
                    this.updateConnectionStatus('error');
                    this.showNotification(`Registration failed: ${event.description}`, 'error');
                }
                break;
        }
    }

    handleIncomingCall(session) {
        if (this.state.inCall) {
            session.hangup();
            return;
        }

        this.sipSession = session;
        const remoteNumber = session.getRemoteFriendlyName() || 'Unknown';
        
        this.state.calling = true;
        this.updateCallInfo(remoteNumber, 'Incoming call...');
        this.showIncomingCallUI();

        session.addEventListener('*', (e) => this.handleCallEvent(e));
    }

    handleCallEvent(event) {
        console.log('Call Event:', event.type, event);

        switch (event.type) {
            case 'connecting':
                this.updateCallInfo(this.state.currentNumber, 'Connecting...');
                break;

            case 'connected':
                this.state.inCall = true;
                this.state.calling = false;
                this.state.callStartTime = Date.now();
                this.startCallTimer();
                this.updateCallInfo(this.state.currentNumber, 'Connected');
                this.enableCallControls();
                this.startAudioVisualization();
                break;

            case 'terminating':
                this.updateCallInfo(this.state.currentNumber, 'Ending call...');
                break;

            case 'terminated':
                this.endCall();
                const reason = event.description || 'Call ended';
                this.showNotification(reason, 'info');
                break;

            case 'i_ao_request':
                if (event.getSipResponseCode() >= 300) {
                    this.endCall();
                    this.showNotification(`Call failed: ${event.description}`, 'error');
                }
                break;
        }
    }

    handleCallAction() {
        if (this.state.inCall) {
            this.hangupCall();
        } else if (this.state.calling) {
            this.hangupCall();
        } else {
            this.makeCall();
        }
    }

    makeCall() {
        if (!this.canMakeCall()) return;

        const number = this.state.currentNumber.trim();
        const sipUri = number.includes('@') ? number : `sip:${number}@${this.config.sip_domain}`;

        try {
            this.sipSession = this.sipStack.newSession('call-audio', {
                video_local: false,
                video_remote: false,
                audio_remote: true,
                events_listener: {
                    events: '*',
                    listener: (e) => this.handleCallEvent(e)
                }
            });

            this.sipSession.call(sipUri);
            this.state.calling = true;
            this.updateCallInfo(number, 'Calling...');
            this.updateCallButton();

        } catch (error) {
            console.error('Call failed:', error);
            this.showNotification('Failed to make call', 'error');
        }
    }

    hangupCall() {
        if (this.sipSession) {
            this.sipSession.hangup();
        }
        this.endCall();
    }

    endCall() {
        this.state.inCall = false;
        this.state.calling = false;
        this.state.callStartTime = null;
        this.stopCallTimer();
        this.stopAudioVisualization();
        this.disableCallControls();
        this.updateCallInfo('', '');
        this.updateCallButton();
        this.sipSession = null;
    }

    answerCall() {
        if (this.sipSession) {
            this.sipSession.accept();
        }
    }

    toggleMute() {
        if (!this.state.inCall) return;

        this.state.muted = !this.state.muted;
        
        if (this.sipSession) {
            if (this.state.muted) {
                this.sipSession.mute('audio');
            } else {
                this.sipSession.unmute('audio');
            }
        }

        this.updateMuteButton();
        this.showNotification(this.state.muted ? 'Microphone muted' : 'Microphone unmuted', 'info');
    }

    toggleSpeaker() {
        this.state.speakerOn = !this.state.speakerOn;
        
        // This would require additional WebRTC API calls for speaker routing
        this.updateSpeakerButton();
        this.showNotification(this.state.speakerOn ? 'Speaker on' : 'Speaker off', 'info');
    }

    handleKeypadPress(digit) {
        if (this.state.inCall && digit !== undefined) {
            // Send DTMF tone
            if (this.sipSession) {
                this.sipSession.dtmf(digit);
            }
            this.playDTMFTone(digit);
        } else {
            // Add to number input
            this.state.currentNumber += digit;
            if (this.elements.numberInput) {
                this.elements.numberInput.value = this.state.currentNumber;
            }
            this.updateCallButton();
        }
    }

    playDTMFTone(digit) {
        // DTMF frequency mapping
        const frequencies = {
            '1': [697, 1209], '2': [697, 1336], '3': [697, 1477],
            '4': [770, 1209], '5': [770, 1336], '6': [770, 1477],
            '7': [852, 1209], '8': [852, 1336], '9': [852, 1477],
            '*': [941, 1209], '0': [941, 1336], '#': [941, 1477]
        };

        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        const freqs = frequencies[digit];
        if (!freqs) return;

        const oscillator1 = this.audioContext.createOscillator();
        const oscillator2 = this.audioContext.createOscillator();
        const gain = this.audioContext.createGain();

        oscillator1.frequency.setValueAtTime(freqs[0], this.audioContext.currentTime);
        oscillator2.frequency.setValueAtTime(freqs[1], this.audioContext.currentTime);
        
        gain.gain.setValueAtTime(0.1, this.audioContext.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + 0.1);

        oscillator1.connect(gain);
        oscillator2.connect(gain);
        gain.connect(this.audioContext.destination);

        oscillator1.start();
        oscillator2.start();
        
        setTimeout(() => {
            oscillator1.stop();
            oscillator2.stop();
        }, 100);
    }

    startCallTimer() {
        this.callTimer = setInterval(() => {
            if (this.state.callStartTime && this.elements.callDuration) {
                const elapsed = Math.floor((Date.now() - this.state.callStartTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                this.elements.callDuration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
        }, 1000);
    }

    stopCallTimer() {
        if (this.callTimer) {
            clearInterval(this.callTimer);
            this.callTimer = null;
        }
        if (this.elements.callDuration) {
            this.elements.callDuration.textContent = '';
        }
    }

    startAudioVisualization() {
        if (this.elements.audioVisualizer) {
            this.elements.audioVisualizer.style.display = 'flex';
        }
    }

    stopAudioVisualization() {
        if (this.elements.audioVisualizer) {
            this.elements.audioVisualizer.style.display = 'none';
        }
    }

    updateConnectionStatus(status) {
        this.state.connectionStatus = status;
        
        const statusMap = {
            'disconnected': { text: 'Disconnected', class: '' },
            'connecting': { text: 'Connecting...', class: 'connecting' },
            'registering': { text: 'Registering...', class: 'connecting' },
            'connected': { text: 'Connected', class: 'connected' },
            'error': { text: 'Error', class: '' },
            'configuration_missing': { text: 'Not configured', class: '' }
        };

        const statusInfo = statusMap[status] || statusMap['disconnected'];
        
        if (this.elements.connectionStatus) {
            this.elements.connectionStatus.textContent = statusInfo.text;
        }
        
        if (this.elements.statusIndicator) {
            this.elements.statusIndicator.className = `status-indicator ${statusInfo.class}`;
        }
    }

    updateCallInfo(number, status) {
        if (this.elements.callNumber) {
            this.elements.callNumber.textContent = number;
        }
        if (this.elements.callStatus) {
            this.elements.callStatus.textContent = status;
        }
    }

    updateCallButton() {
        if (!this.elements.btnCall) return;

        if (this.state.inCall) {
            this.elements.btnCall.className = 'btn-call hangup';
            this.elements.btnCall.innerHTML = '<span class="icon">✖</span>';
            this.elements.btnCall.disabled = false;
        } else if (this.state.calling) {
            this.elements.btnCall.className = 'btn-call hangup';
            this.elements.btnCall.innerHTML = '<span class="icon">✖</span>';
            this.elements.btnCall.disabled = false;
        } else {
            this.elements.btnCall.className = 'btn-call';
            this.elements.btnCall.innerHTML = '<span class="icon">📞</span>';
            this.elements.btnCall.disabled = !this.canMakeCall();
        }
    }

    updateMuteButton() {
        if (this.elements.btnMute) {
            this.elements.btnMute.classList.toggle('active', this.state.muted);
        }
    }

    updateSpeakerButton() {
        if (this.elements.btnSpeaker) {
            this.elements.btnSpeaker.classList.toggle('active', this.state.speakerOn);
        }
    }

    enableCallControls() {
        [this.elements.btnMute, this.elements.btnSpeaker, this.elements.btnTransfer]
            .forEach(btn => btn && (btn.disabled = false));
    }

    disableCallControls() {
        [this.elements.btnMute, this.elements.btnSpeaker, this.elements.btnTransfer]
            .forEach(btn => btn && (btn.disabled = true));
        
        this.state.muted = false;
        this.state.speakerOn = false;
        this.updateMuteButton();
        this.updateSpeakerButton();
    }

    canMakeCall() {
        return this.state.registered && 
               this.state.currentNumber.trim().length > 0 && 
               !this.state.calling && 
               !this.state.inCall;
    }

    showSettings() {
        if (this.elements.settingsPanel) {
            this.elements.settingsPanel.style.display = 'flex';
            this.populateSettingsForm();
        }
    }

    hideSettings() {
        if (this.elements.settingsPanel) {
            this.elements.settingsPanel.style.display = 'none';
        }
    }

    populateSettingsForm() {
        const form = this.elements.settingsForm;
        if (!form) return;

        Object.keys(this.config).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                input.value = this.config[key] || '';
            }
        });
    }

    saveSettings() {
        const form = this.elements.settingsForm;
        if (!form) return;

        const formData = new FormData(form);
        const newConfig = {};

        for (let [key, value] of formData.entries()) {
            newConfig[key] = value;
        }

        this.config = { ...this.config, ...newConfig };
        
        // Save to localStorage
        localStorage.setItem('sipClientConfig', JSON.stringify(this.config));
        
        this.hideSettings();
        this.showNotification('Settings saved', 'success');
        
        // Restart SIP stack with new config
        if (this.sipStack) {
            this.sipStack.stop();
            setTimeout(() => this.createSipStack(), 1000);
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span class="icon">${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
            <span>${message}</span>
        `;

        document.body.appendChild(notification);
        
        setTimeout(() => notification.classList.add('show'), 100);
        
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => document.body.removeChild(notification), 300);
        }, 4000);
    }

    handleKeyboardShortcuts(event) {
        if (event.ctrlKey || event.metaKey) return;

        // Handle numeric keypad
        if (event.key >= '0' && event.key <= '9' || event.key === '*' || event.key === '#') {
            this.handleKeypadPress(event.key);
            event.preventDefault();
        }

        // Handle function keys
        switch (event.key) {
            case 'Enter':
                if (this.canMakeCall()) this.handleCallAction();
                break;
            case 'Escape':
                if (this.state.inCall || this.state.calling) this.hangupCall();
                break;
            case 'm':
            case 'M':
                if (this.state.inCall) this.toggleMute();
                break;
        }
    }

    startConnectionMonitoring() {
        // Monitor connection status periodically
        setInterval(() => {
            if (this.sipStack && this.state.registered) {
                // Could add ping/keepalive logic here
            }
        }, 30000);
    }

    destroy() {
        if (this.sipStack) {
            this.sipStack.stop();
        }
        if (this.callTimer) {
            clearInterval(this.callTimer);
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Get config from Django template context
    let config = {};
    try {
        const configElement = document.getElementById('sip-config');
        if (configElement) {
            config = JSON.parse(configElement.textContent);
        }
    } catch (e) {
        console.warn('Could not parse SIP configuration:', e);
    }

    // Load saved settings from localStorage
    try {
        const savedConfig = localStorage.getItem('sipClientConfig');
        if (savedConfig) {
            config = { ...config, ...JSON.parse(savedConfig) };
        }
    } catch (e) {
        console.warn('Could not load saved configuration:', e);
    }

    // Initialize SIP client
    window.sipClient = new ModernSipClient(config);
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernSipClient;
}