(function(){
  function $(sel, root){ return (root||document).querySelector(sel); }
  function $all(sel, root){ return Array.prototype.slice.call((root||document).querySelectorAll(sel)); }
  function on(el, ev, fn){ el && el.addEventListener(ev, fn); }
  function log(){ if (window.SIPML_UI && SIPML_UI.log) SIPML_UI.log.apply(null, arguments); }

  var $status = $('#status');
  var tones = { ringtone: $('#ringtone'), ringback: $('#ringbacktone'), dtmf: $('#dtmfTone') };

  function setStatus(text, color){ if ($status){ $status.textContent = text; if (color) { $status.style.color = color; } } }
  function setButtonsConnected(v){ var a=['login_btn','logout_btn']; $('#login_btn').disabled=!!v; $('#logout_btn').disabled=!v; }
  function setButtonsIncall(v){ $('#call_btn').disabled=!!v; $('#hangup_btn').disabled=!v; }
  function setMuted(v){ var b=$('#mute_btn'); if (b) b.textContent = v ? (b.dataset.txtUnmute||'Unmute') : (b.dataset.txtMute||'Mute'); }
  function play(t){ var el = tones[t]; if (el){ try{ el.currentTime=0; el.play(); }catch(e){} } }
  function stop(t){ var el = tones[t]; if (el){ try{ el.pause(); el.currentTime=0; }catch(e){} } }

  // Tabs
  $all('[data-tab]').forEach(function(tab){
    on(tab, 'click', function(){
      var name = tab.getAttribute('data-tab');
      $all('.tab').forEach(function(t){ t.classList.toggle('active', t===tab); });
      $all('.tabpane').forEach(function(p){ p.classList.toggle('active', p.getAttribute('data-pane')===name); });
    });
  });

  // Keypad
  $all('.dial').forEach(function(btn){
    on(btn, 'click', function(){
      var t = $('#target');
      t.value = (t.value || '') + btn.getAttribute('data-val');
      play('dtmf');
    });
  });

  // Lines
  $all('.line').forEach(function(btn){
    on(btn, 'click', function(){
      $all('.line').forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      var n = parseInt(btn.getAttribute('data-line'),10)||1;
      if (window.Phone && Phone.selectLine) Phone.selectLine(n);
      log('Active line', n);
    });
  });

  // Modals
  function modal(id){ return { el: $(id), open: function(){ this.el.style.display='flex'; }, close: function(){ this.el.style.display='none'; } }; }
  var settings = modal('#modal-settings');
  var transfer = modal('#modal-transfer');
  on($('#btn-open-settings'), 'click', function(){ settings.open(); });
  $all('#modal-settings .close').forEach(function(b){ on(b,'click', function(){ settings.close(); }); });
  on($('#btn-open-transfer'), 'click', function(){ transfer.open(); });
  $all('#modal-transfer .close').forEach(function(b){ on(b,'click', function(){ transfer.close(); }); });
  // Transfer OK button (first .close in modal-footer)
  var transferOk = (function(){ var btns = $all('#modal-transfer .btn.btn-success'); return btns[0]; })();
  on(transferOk, 'click', function(){ var num = $('#transfer-number').value; if (window.Phone && Phone.transfer && num){ Phone.transfer(num); } transfer.close(); });

  // Wire to Phone if available
  on($('#login_btn'), 'click', function(){ if (window.Phone && Phone.login) Phone.login(); });
  on($('#logout_btn'), 'click', function(){ if (window.Phone && Phone.logout) Phone.logout(); });
  on($('#call_btn'), 'click', function(){ if (window.Phone && Phone.call) Phone.call(); });
  on($('#hangup_btn'), 'click', function(){ if (window.Phone && Phone.hangup) Phone.hangup(); });
  on($('#mute_btn'), 'click', function(){ if (window.Phone && Phone.toggleMute) Phone.toggleMute(); });

  // API for Phone to update UI
  window.SIPML_UI_API = {
    setConnected: function(v){ setButtonsConnected(v); setStatus(v? 'Connected':'Disconnected'); if (!v){ stop('ringtone'); stop('ringback'); setButtonsIncall(false);} },
    setRinging: function(dir){ setStatus(dir==='in'?'Incoming…':'Calling…'); if (dir==='in'){ play('ringtone'); } else { play('ringback'); } },
    stopRinging: function(){ stop('ringtone'); stop('ringback'); },
    setInCall: function(v){ setButtonsIncall(v); if (v){ this.stopRinging(); } },
    setMuted: function(v){ setMuted(v); },
    setError: function(msg){ setStatus('Error'); log('Error:', msg); this.stopRinging(); }
  };
})();
