	var Phone;
	var sTransferNumber;
	var oRingTone, oRingbackTone;
	var oSipStack = oSipSessionRegister = oSipSessionCall = oSipSessionTransferCall = null;
	var audioRemote;
	var oNotifICall;
	var oConfigCall;
	var oReadyStateTimer;
	var phoneNumber;
	var phoneUser;
	var phoneState;
	var onCreateOrder = null;

$(function () {
	audioRemote = $("#audio_remote").get(0);
	Phone = $('#phone');
	// set debug level
	SIPml.setDebugLevel("info");

	oReadyStateTimer = setInterval(function () {
		if (document.readyState === "complete") {
			clearInterval(oReadyStateTimer);
			// initialize SIPML5
			SIPml.init(postInit);
			state(0);
		}
	},
	500);

	if (!window.WebSocket || navigator.appName == "Microsoft Internet Explorer")
		$("#txtWebsocketServerUrl").attr('disabled', "disabled"); // Do not use WS on IE

	if(localStorage){
		if (localStorage['phone.enable_rtcweb_breaker'])
			settingsRevert(true);
		else
			settingsSave();
	} else {
		$("#btnSave").attr('disabled', "disabled");
		$("#btnRevert").attr('disabled', "disabled");
	}

	Phone.find(".phone-number").keydown(function (event) {
		if ((event.keyCode || event.which) == 13)
			sipCall('call-audio');
	})
	.focus(function () {if (phoneNumber == "")	$(this).val("");})
	.blur(function () {phoneNumber = $(this).val();});

	$("#btnSave").click(settingsSave);

	$("#btnRevert").click(settingsRevert);

	Phone.find(".phone-show-expert").click(function (e) {
		e.preventDefault();
		show_expert();
		return false;
	});

	Phone.find(".phone-hide-expert").click(function (e) {
		e.preventDefault();
		hide_expert();
		return false;
	});

	Phone.find(".phone-hide-transfer").click(function (e) {
		e.preventDefault();
		Phone.find(".phone-modal-transfer").addClass("hide");
		return false;
	});

	Phone.find(".phone-transfer-ok").click(function (e) {
		var number = Phone.find(".transfer-number").val();
		if (console)
			console.log(">transfer number=" + number);

		if (number && number.length > 0) {
			sipTransfer(number);
			Phone.find(".phone-modal-transfer").addClass("hide");
		}
		return false;
	});

	Phone.find(".phone-content .btn").click(function () {
		var value = $(this).val();
		switch (value) {
			case "login":	sipRegister();	break;
			case "logout":	hide_expert(); sipUnRegister();	break;
			case "call":	sipCall('call-audio');	break;
			case "answer":
				var in_phone = Phone.find(".phone-number").val();
				sipCall();
				onCreateOrder(in_phone);
				break;
			// case "records":	records();break;
			case "handup":	sipHangUp();	break;
			case "hold":	sipToggleHoldResume();	break;
			case "delete":	if (oSipStack!==null) delete_number();	break;
			case "transfer":
				Phone.find(".phone-modal-transfer").removeClass("hide");
				Phone.find(".transfer-number").val("");
				Phone.find(".transfer-number").focus();
				break;
			default:
				if (oSipStack!==null) {
					sipSendDTMF(value);
					add_number(value);
				}
				break;
		}
	});

	$(window).keydown(function (e) {
		switch (e.keyCode || e.which) {
			case 27: //F11
				sipHangUp();
				break;

			case 32: //F12
				//incall
				var in_phone = Phone.find(".phone-number").val();
				sipCall();
				onCreateOrder(in_phone);
				break;
		}
	});
});
	function add_number(v) {
		phoneNumber = phoneNumber + v;
		phone_number(phoneNumber);
		phone_status("");
	}

	function delete_number() {
		if (phoneNumber.length > 0 && phoneNumber.length < 20) {
			phoneNumber = phoneNumber.substring(0, phoneNumber.length - 1);
			phone_number(phoneNumber);
		}

		if (phoneNumber.length == 0) {
			my_number();
		}
	}

	function call(number) {
		phone_number(number);
		sipCall('call-audio');
	}
	
	function state(i) {
		switch (i) {
			case 0:
				phoneNumber = "";
				phone_number("");
				phone_status("Телефон выключен");
				Phone.find(".phone-btn-contanier-call").hide();
				Phone.find(".phone-btn-contanier-delete").hide();
				Phone.find(".phone-btn-contanier-logout").hide();
				Phone.find(".phone-btn-contanier-login").show();
				Phone.find(".phone-number").attr("readonly", "readonly");
				Phone.find(".nav-tabs").show();
				Phone.find(".phone-contanier-handup").hide();
				Phone.find(".phone-contanier-default").show();
				Phone.find(".phone-contanier-incall").hide();
				Phone.find(".phone-contanier-numbers").show();
				Phone.find(".phone-dial").hide();
				
				break;

			case 1: // Готов звонить
				phoneNumber = "";
				my_number();
				Phone.find(".phone-btn-contanier-call").show();
				Phone.find(".phone-btn-contanier-delete").show();
				Phone.find(".phone-btn-contanier-logout").show();
				Phone.find(".phone-btn-contanier-login").hide();
				Phone.find(".phone-number").removeAttr("readonly");
				Phone.find(".nav-tabs").show();
				Phone.find(".phone-contanier-handup").hide();
				Phone.find(".phone-contanier-default").show();
				Phone.find(".phone-contanier-incall").hide();
				Phone.find(".phone-contanier-numbers").show();
				Phone.find(".phone-dial").hide();
				break;

			case 2:	//Входящий звонок
				phone_status("");
				Phone.find(".phone-number").attr("readonly", "readonly");
				Phone.find(".nav-tabs").hide();
				Phone.find(".phone-contanier-default").hide();
				Phone.find(".phone-contanier-handup").hide();
				Phone.find(".phone-contanier-numbers").hide();
				Phone.find(".phone-contanier-incall").show();
				Phone.find(".phone-dial").hide();
				break;

			case 3:	//call
				phone_status("Звоним");
				Phone.find(".phone-number").attr("readonly", "readonly");
				Phone.find(".nav-tabs").hide();
				Phone.find(".phone-contanier-default").hide();
				Phone.find(".phone-contanier-handup").show();
				Phone.find(".phone-contanier-numbers").show();
				Phone.find(".phone-contanier-incall").hide();
				Phone.find(".phone-dial").hide();
				break;
		}
		phoneState = i;
	}
	function my_number() {
		phone_status("Мой номер");
		phone_number(phoneUser);
	}
	
	function show_expert() {
		Phone.find(".phone-expert-contanier")
			.removeClass("modal-hide")
			.addClass("modal");
		return false;
	}

	function hide_expert() {
		Phone.find(".phone-expert-contanier")
			.removeClass("modal")
			.addClass("modal-hide");
		return false;
	}
	
	function settingsSave() {
		localStorage['phone.enable_rtcweb_breaker']		= $("#cbRTCWebBreaker").is(":checked") ? "true" : "false";
		if (!$("#txtWebsocketServerUrl").is(":disabled"))
			localStorage['phone.websocket_server_url']	= $("#txtWebsocketServerUrl").val();
		localStorage['phone.sip_outboundproxy_url']		= $("#txtSIPOutboundProxyUrl").val();
		localStorage['phone.ice_servers']				= $("#txtIceServers").val();
		localStorage['phone.bandwidth']					= $("#txtBandwidth").val();
		localStorage['phone.disable_early_ims'] 		= $("#cbEarlyIMS").is(":checked") ? "true" : "false";
		localStorage['phone.enable_media_caching']		= $("#cbCacheMediaStream").is(":checked") ? "true" : "false";

		Phone.find("#txtInfo").html('Сохранено');
	}

	function settingsRevert(bNotUserAction) {
		$("#cbRTCWebBreaker").prop("checked",	localStorage['phone.enable_rtcweb_breaker'] == "true");
		$("#txtWebsocketServerUrl").val(		localStorage['phone.websocket_server_url'] || "");
		$("#txtSIPOutboundProxyUrl").val(		localStorage['phone.sip_outboundproxy_url'] || "");
		$("#txtIceServers").val(				localStorage['phone.ice_servers'] || "");
		$("#txtBandwidth").val(					localStorage['phone.bandwidth'] || "");
		$("#cbEarlyIMS").prop("checked", 		localStorage['phone.disable_early_ims'] == "true");
		$("cbCacheMediaStream").prop("checked", localStorage['phone.enable_media_caching'] == "true");

		if (!bNotUserAction) Phone.find("#txtInfo").html('Восстановлено');
	}

	// sends SIP REGISTER request to login
	function sipRegister() {
		// catch exception for IE (DOM not ready)
		try {
			enable_btn_login(true);
			Phone.find(".phone-index").tab('show');
			$.ajax({
				type: "POST",
				url: "/phone/login",
				timeout: 15000,
				success: function (data) {
					try {
						if (data && data.Login && data.Password && Phone.data("server") && data.Sip) {
							//console.log(data);
							var guid = data.Login.replace("@", "_").replace(/\./g, "_").trim();
							if (guid) {
								Phone.attr("guid", guid);

								Phone.find(".input-login").val(data.Login);
								Phone.find(".input-password").val(data.Password);
								Phone.find(".input-sip").val(data.Sip);
								var o_impu = tsip_uri.prototype.Parse(data.Sip);
								if (!o_impu || !o_impu.s_user_name || !o_impu.s_host)
									return "Sip некорректен";

								// enable notifications if not already done
								if (window.webkitNotifications && window.webkitNotifications.checkPermission() != 0)
									window.webkitNotifications.requestPermission();

								// update debug level to be sure new values will be used if the user haven't updated the page
								SIPml.setDebugLevel("info");

								// create SIP stack
								oSipStack = new SIPml.Stack({
									realm: Phone.data("server"),
									impi: data.Login,
									impu: data.Sip,
									password: data.Password,
									display_name: data.Login,
									websocket_proxy_url:		(localStorage ? localStorage['phone.websocket_server_url'] : null),
									outbound_proxy_url:			(localStorage ? localStorage['phone.sip_outboundproxy_url'] : null),
									ice_servers:				(localStorage ? localStorage['phone.ice_servers'] : null),
									enable_rtcweb_breaker:		(localStorage ? localStorage['phone.enable_rtcweb_breaker'] == "true" : false),
									enable_media_stream_cache:	(localStorage ? localStorage['phone.enable_media_caching'] == "true" : false),
									enable_early_ims:			(localStorage ? localStorage['phone.disable_early_ims'] != "true" : true), // Must be true unless you're using a real IMS network
									bandwidth:					(localStorage ? tsk_string_to_object(localStorage['phone.bandwidth']) : null), // could be redefined a session-level
									events_listener:			{events: '*', listener: onSipEventStack},
									sip_headers:				[{name: 'User-Agent', value: 'IM-client/OMA1.0 sipML5-v1.2015.03.18' },{name: 'Organization', value: 'Doubango Telecom'}]
								});
								var result = oSipStack.start() == 0;
								if (result) {
									phoneUser = data.Login;
									enable_btn_login(false);
									state(1);
								}
								return !result ? 'Ошибка регистрации' : 'ok';
							}
						}
						else if (!data.Login || !data.Password) {
							phone_status("Не указан логин или пароль");
							enable_btn_login(true);
						}
						else {
							localStorage.removeItem("phone.login");
						}
					}
					catch (e) {
						if (console)
							console.error(e);
						enable_btn_login(true);
					}
				},
				error: function () {
					phone_status("Ошибка подключения");
					enable_btn_login(true);
				}
			});

		}
		catch (e) {
			return "Ошибка:" + e;
		}
	}

	function postInit() {
		// check webrtc4all version
		if (SIPml.isWebRtc4AllSupported() && SIPml.isWebRtc4AllPluginOutdated()) {
			if (confirm("Your WebRtc4all extension is outdated ("+SIPml.getWebRtc4AllVersion()+"). A new version with critical bug fix is available. Do you want to install it?\nIMPORTANT: You must restart your browser after the installation.")) {
				window.location = 'http://code.google.com/p/webrtc4all/downloads/list';
				return;
			}
		}

		// check for WebRTC support
		if (!SIPml.isWebRtcSupported()) {
			// is it chrome?
			if (SIPml.getNavigatorFriendlyName() == 'chrome') {
				if (confirm("You're using an old Chrome version or WebRTC is not enabled.\nDo you want to see how to enable WebRTC?")) {
					window.location = 'http://www.webrtc.org/running-the-demos';
				}
				return;
			}

			// for now the plugins (WebRTC4all only works on Windows)
			if (SIPml.getSystemFriendlyName() == 'windows') {
				// Internet explorer
				if (SIPml.getNavigatorFriendlyName() == 'ie') {
					// Check for IE version
					if (parseFloat(SIPml.getNavigatorVersion()) < 9.0) {
						if (confirm("You are using an old IE version. You need at least version 9. Would you like to update IE?")) {
							window.location = 'http://windows.microsoft.com/en-us/internet-explorer/products/ie/home';
						}
					}

					// check for WebRTC4all extension
					if (!SIPml.isWebRtc4AllSupported()) {
						if (confirm("webrtc4all extension is not installed. Do you want to install it?\nIMPORTANT: You must restart your browser after the installation.")) {
							window.location = 'http://code.google.com/p/webrtc4all/downloads/list';
						}
					}
					// break page loading ('window.location' won't stop JS execution)
					if (!SIPml.isWebRtc4AllSupported()) {
						return;
					}
				}
				else if (SIPml.getNavigatorFriendlyName() == "safari" || SIPml.getNavigatorFriendlyName() == "firefox" || SIPml.getNavigatorFriendlyName() == "opera") {
					if (confirm("Your browser don't support WebRTC.\nDo you want to install WebRTC4all extension to enjoy audio/video calls?\nIMPORTANT: You must restart your browser after the installation.")) {
						window.location = 'http://code.google.com/p/webrtc4all/downloads/list';
					}
					return;
				}
			}
			// OSX, Unix, Android, iOS...
			else {
				if (confirm('WebRTC not supported on your browser.\nDo you want to download a WebRTC-capable browser?')) {
					window.location = 'https://www.google.com/intl/en/chrome/browser/';
				}
				return;
			}
		}

		// checks for WebSocket support
		if (!SIPml.isWebSocketSupported() && !SIPml.isWebRtc4AllSupported()) {
			if (confirm('Your browser don\'t support WebSockets.\nDo you want to download a WebSocket-capable browser?')) {
				window.location = 'https://www.google.com/intl/en/chrome/browser/';
			}
			return;
		}

		// FIXME: displays must be per session

		if (!SIPml.isWebRtc4AllSupported() && !SIPml.isWebRtcSupported()) {
			if (confirm('Your browser don\'t support WebRTC.\naudio/video calls will be disabled.\nDo you want to download a WebRTC-capable browser?')) {
				window.location = 'https://www.google.com/intl/en/chrome/browser/';
			}
		}

		enable_btn_login(true);
		document.body.style.cursor = 'default';
		oConfigCall = {
			audio_remote: audioRemote,
			bandwidth: { audio:undefined, video:undefined },
			events_listener: { events: '*', listener: onSipEventSession },
			sip_caps: [
							{ name: '+g.oma.sip-im' },
							{ name: 'language', value: '\"en,fr\"' }
						]
		};
		
		sipRegister();
	}
	
	function phone_number(number) {
		Phone.find(".phone-number").val(number);
	}
	
	function enable_btn_login(enable) {
		if (enable) {
			Phone.find(".phone-btn-contanier-login")
				.find("button")
				.removeAttr("disabled")
				.removeClass("btn-default-gray")
				.addClass("btn-default-green");
		}
		else {
			Phone.find(".phone-btn-contanier-login")
				.find("button")
				.attr("disabled", "disabled")
				.removeClass("btn-default-green")
				.addClass("btn-default-gray");
		}
		// Update new UI
		if (window.SIPML_UI_API) {
			window.SIPML_UI_API.setConnected(!enable);
		}
	}
	
	function disable_btn(btn, disable) {
		btn = Phone.find('.btn [value='+btn+']');
		if (btn)
			if (disable)
				btn.attr("disabled", "disabled");
			else
				btn.removeAttr("disabled");
	}
	function phone_status(status) {
		Phone.find(".phone-status").text(status);
		// Update new UI
		if (window.SIPML_UI_API && status) {
			if (status.includes('Входящий звонок') || status.includes('Incoming call')) {
				window.SIPML_UI_API.setRinging('in');
			} else if (status.includes('Звоним') || status.includes('Calling')) {
				window.SIPML_UI_API.setRinging('out');
			} else if (status.includes('Ошибка') || status.includes('Failed') || status.includes('Error')) {
				window.SIPML_UI_API.setError(status);
			}
		}
	}

	// sends SIP REGISTER (expires=0) to logout
	function sipUnRegister() {
		state(0);
		if (oSipStack) {
			oSipStack.stop(); // shutdown all sessions
			phoneUser = '';
		}
	}

	// makes a call (SIP INVITE)
	function sipCall(s_type) {
		if (oSipStack && !oSipSessionCall && !tsk_string_is_null_or_empty(Phone.find(".phone-number").val())) {
			disable_btn('call', true);
			disable_btn('hangup', false);

			if(localStorage) {
				oConfigCall.bandwidth = tsk_string_to_object(localStorage['phone.bandwidth']); // already defined at stack-level but redifined to use latest values
			}

			// create call session
			oSipSessionCall = oSipStack.newSession(s_type, oConfigCall);
			// make call
			if (oSipSessionCall.call(Phone.find(".phone-number").val()) != 0) {
				oSipSessionCall = null;
				phone_status('Ошибка соединения');
				disable_btn('call', false);
				disable_btn('hangup', true);
				state(1);
				return;
			}
			state(3);
		}
		else if (oSipSessionCall) {
			phone_status('Соединяю...');
			oSipSessionCall.accept(oConfigCall);
			state(2);
		}
	}

	// transfers the call
	function sipTransfer(s_destination) {
		if (oSipSessionCall) {
			if (!tsk_string_is_null_or_empty(s_destination)) {
				disable_btn('transfer', true);
				if (oSipSessionCall.transfer(s_destination) != 0) {
					phone_status('Ошибка перенаправления');
					disable_btn('transfer', false);
					return;
				}
				phone_status('Перенаправление...');
			}
		}
	}

	// holds or resumes the call
	function sipToggleHoldResume() {
		if (oSipSessionCall) {
			var i_ret;
			disable_btn('hold', true);
			phone_status(oSipSessionCall.bHeld ? 'Возврат...' : 'Удержание...');
			i_ret = oSipSessionCall.bHeld ? oSipSessionCall.resume() : oSipSessionCall.hold();
			if (i_ret != 0) {
				phone_status('Ошибка удержания');
				disable_btn('hold', false);
				return;
			}
		}
	}

	// Mute or Unmute the call
	function sipToggleMute() {
		if (oSipSessionCall) {
			var i_ret;
			var bMute = !oSipSessionCall.bMute;
			phone_status(bMute ? 'Mute the call...' : 'Unmute the call...');
			i_ret = oSipSessionCall.mute('audio', bMute);
			if (i_ret != 0) {
				phone_status('Mute / Unmute failed');
				return;
			}
			oSipSessionCall.bMute = bMute;
			// Update new UI
			if (window.SIPML_UI_API) {
				window.SIPML_UI_API.setMuted(bMute);
			}
		}
	}

	// terminates the call (SIP BYE or CANCEL)
	function sipHangUp() {
		if (oSipSessionCall) {
			phone_status('Рассоединяю...');
			oSipSessionCall.hangup({events_listener: { events: '*', listener: onSipEventSession }});
		}
		state(1);
		// Update new UI
		if (window.SIPML_UI_API) {
			window.SIPML_UI_API.stopRinging();
			window.SIPML_UI_API.setInCall(false);
		}
	}

	function sipSendDTMF(c){
		if(oSipSessionCall && c){
			if(oSipSessionCall.dtmf(c) == 0){
				try { dtmfTone.play(); } catch(e){ }
			}
		}
	}

	function startRingTone() {
		try { ringtone.play(); }
		catch (e) { }
	}

	function stopRingTone() {
		try { ringtone.pause(); }
		catch (e) { }
	}

	function startRingbackTone() {
		try { ringbacktone.play(); }
		catch (e) { }
	}

	function stopRingbackTone() {
		try { ringbacktone.pause(); }
		catch (e) { }
	}

	function showNotifICall(s_number) {
		// permission already asked when we registered
		if (window.webkitNotifications && window.webkitNotifications.checkPermission() == 0) {
			if (oNotifICall) {
				oNotifICall.cancel();
			}
			oNotifICall = window.webkitNotifications.createNotification('images/sipml-34x39.png', 'Incaming call', 'Incoming call from ' + s_number);
			oNotifICall.onclose = function () { oNotifICall = null; };
			oNotifICall.show();
		}
	}

	function uiOnConnectionEvent(b_connected, b_connecting) { // should be enum: connecting, connected, terminating, terminated
		enable_btn_login(!b_connected && !b_connecting);
		// btnRegister.disabled = b_connected || b_connecting;
		// btnUnRegister.disabled = !b_connected && !b_connecting;
		disable_btn('call', !(b_connected && tsk_utils_have_webrtc() && tsk_utils_have_stream()));
		disable_btn('handup', !oSipSessionCall);
	}

	function uiCallTerminated(s_description){
		disable_btn('call', false);
		disable_btn('hangup', true);
		state(1);
		if (window.btnBFCP) window.btnBFCP.disabled = true;

		oSipSessionCall = null;

		stopRingbackTone();
		stopRingTone();

		phone_status(s_description);

		if (oNotifICall) {
			oNotifICall.cancel();
			oNotifICall = null;
		}

		setTimeout(function () { if (!oSipSessionCall) state(1); }, 2500);
	}

	// Callback function for SIP Stacks
	function onSipEventStack(e /*SIPml.Stack.Event*/) {
		tsk_utils_log_info('==stack event = ' + e.type);
		switch (e.type) {
			case 'started':
				{
					// catch exception for IE (DOM not ready)
					try {
						// LogIn (REGISTER) as soon as the stack finish starting
						oSipSessionRegister = this.newSession('register', {
							expires: 200,
							events_listener: { events: '*', listener: onSipEventSession },
							sip_caps: [
										{ name: '+g.oma.sip-im', value: null },
										//{ name: '+sip.ice' }, // rfc5768: FIXME doesn't work with Polycom TelePresence
										{ name: '+audio', value: null },
										{ name: 'language', value: '\"en,fr\"' }
								]
						});
						oSipSessionRegister.register();
					}
					catch (e) {
						phone_status(e);
						enable_btn_login(true);
					}
					break;
				}
			case 'stopping': case 'stopped': case 'failed_to_start': case 'failed_to_stop':
				{
					var bFailure = (e.type == 'failed_to_start') || (e.type == 'failed_to_stop');
					oSipStack = null;
					oSipSessionRegister = null;
					oSipSessionCall = null;

					uiOnConnectionEvent(false, false);

					stopRingbackTone();
					stopRingTone();

					phone_status(bFailure ? "Отключен: " + e.description : "Отключен");
					break;
				}

			case 'i_new_call':
				{
					if (oSipSessionCall) {
						// do not accept the incoming call if we're already 'in call'
						// e.newSession.hangup(); // comment this line for multi-line support
					}
					else {
						oSipSessionCall = e.newSession;
						// start listening for events
						oSipSessionCall.setConfiguration(oConfigCall);

						disable_btn('call', false);
						disable_btn('hangup', false);

						startRingTone();

						var sRemoteNumber = (oSipSessionCall.getRemoteFriendlyName() || 'unknown');
						showNotifICall(sRemoteNumber);
						state(2);
						phone_number(sRemoteNumber);
						phone_status("Входящий звонок");
					}
					break;
				}

			case 'm_permission_requested':
				{
					break;
				}
			case 'm_permission_accepted':
			case 'm_permission_refused':
				{
					if(e.type == 'm_permission_refused'){
						uiCallTerminated('Media stream permission denied');
					}
					break;
				}

			case 'starting': default: break;
		}
	};

	// Callback function for SIP sessions (INVITE, REGISTER, MESSAGE...)
	function onSipEventSession(e /* SIPml.Session.Event */) {
		tsk_utils_log_info('==session event = ' + e.type);

		switch (e.type) {
			case 'connecting': case 'connected':
				{
					var bConnected = (e.type == 'connected');
					if (e.session == oSipSessionRegister) {
						uiOnConnectionEvent(bConnected, !bConnected);
						phone_status(e.description);
						state(1);
					}
					else if (e.session == oSipSessionCall) {
						disable_btn('call', true);
						disable_btn('hangup', false);
						disable_btn('transfer', false);
						state(3);
						if (window.btnBFCP) window.btnBFCP.disabled = false;

						if (bConnected) {
							stopRingbackTone();
							stopRingTone();

							if (oNotifICall) {
								oNotifICall.cancel();
								oNotifICall = null;
							}
						}

						phone_status(e.description);

					}
					break;
				} // 'connecting' | 'connected'
			case 'terminating': case 'terminated':
				{
					if (e.session == oSipSessionRegister) {
						uiOnConnectionEvent(false, false);

						oSipSessionCall = null;
						oSipSessionRegister = null;

						phone_status(e.description);
					}
					else if (e.session == oSipSessionCall) {
						uiCallTerminated(e.description);
					}
					break;
				} // 'terminating' | 'terminated'

			case 'm_stream_video_local_added':
			case 'm_stream_video_local_removed':
			case 'm_stream_video_remote_added':
			case 'm_stream_video_remote_removed':

			case 'm_stream_audio_local_added':
			case 'm_stream_audio_local_removed':
			case 'm_stream_audio_remote_added':
			case 'm_stream_audio_remote_removed':
				{
					break;
				}

			case 'i_ect_new_call':
				{
					oSipSessionTransferCall = e.session;
					break;
				}

			case 'i_ao_request':
				{
					if(e.session == oSipSessionCall){
						var iSipResponseCode = e.getSipResponseCode();
						if (iSipResponseCode == 180 || iSipResponseCode == 183) {
							startRingbackTone();
							phone_status('Входящий звонок...');
							state(2);
						}
					}
					break;
				}

			case 'm_early_media':
				{
					if(e.session == oSipSessionCall){
						stopRingbackTone();
						stopRingTone();
						phone_status('Early media started');
					}
					break;
				}

			case 'm_local_hold_ok':
				{
					if(e.session == oSipSessionCall){
						if (oSipSessionCall.bTransfering) {
							oSipSessionCall.bTransfering = false;
							// this.AVSession.TransferCall(this.transferUri);
						}
						disable_btn('hold', false);
						phone_status('Удеражание');
						oSipSessionCall.bHeld = true;
					}
					break;
				}
			case 'm_local_hold_nok':
				{
					if(e.session == oSipSessionCall){
						oSipSessionCall.bTransfering = false;
						disable_btn('hold', false);
						phone_status('Failed to place remote party on hold');
					}
					break;
				}
			case 'm_local_resume_ok':
				{
					if(e.session == oSipSessionCall){
						oSipSessionCall.bTransfering = false;
						disable_btn('hold', false);
						phone_status('Возврат звонка');
						oSipSessionCall.bHeld = false;

					}
					break;
				}
			case 'm_local_resume_nok':
				{
					if(e.session == oSipSessionCall){
						oSipSessionCall.bTransfering = false;
						disable_btn('hold', false);
						phone_status('Ошибка возврата');
					}
					break;
				}
			case 'm_remote_hold':
				{
					if(e.session == oSipSessionCall){
						phone_status('Удержание абонентом');
					}
					break;
				}
			case 'm_remote_resume':
				{
					if(e.session == oSipSessionCall){
						phone_status('Возврат звонка');
					}
					break;
				}
			case 'm_bfcp_info':
				{
					if(e.session == oSipSessionCall){
						phone_status('BFCP Info: '+ e.description);
					}
					break;
				}

			case 'o_ect_trying':
				{
					if(e.session == oSipSessionCall){
						phone_status('Перенаправление...');
					}
					break;
				}
			case 'o_ect_accepted':
				{
					if(e.session == oSipSessionCall){
						phone_status('Перенаправление принято');
					}
					break;
				}
			case 'o_ect_completed':
			case 'i_ect_completed':
				{
					if(e.session == oSipSessionCall){
						phone_status('Перенаправление завершено');
						disable_btn('transfer', false);
						if (oSipSessionTransferCall) {
							oSipSessionCall = oSipSessionTransferCall;
						}
						oSipSessionTransferCall = null;
					}
					break;
				}
			case 'o_ect_failed':
			case 'i_ect_failed':
				{
					if(e.session == oSipSessionCall){
						phone_status('Ошибка перенаправления');
						disable_btn('transfer', false);
					}
					break;
				}
			case 'o_ect_notify':
			case 'i_ect_notify':
				{
					if(e.session == oSipSessionCall){
						phone_status("Перенаправление: " + e.getSipResponseCode() + " " + e.description);
						if (e.getSipResponseCode() >= 300) {
							if (oSipSessionCall.bHeld) {
								oSipSessionCall.resume();
							}
							disable_btn('transfer', false);
						}
					}
					break;
				}
			case 'i_ect_requested':
				{
					if(e.session == oSipSessionCall){
						var s_message = "Принять перенаправленный звонок [" + e.getTransferDestinationFriendlyName() + "]?";//FIXME
						if (confirm(s_message)) {
							phone_status("Перенаправление...");
							oSipSessionCall.acceptTransfer();
							break;
						}
						oSipSessionCall.rejectTransfer();
					}
					break;
				}
		}
	}
