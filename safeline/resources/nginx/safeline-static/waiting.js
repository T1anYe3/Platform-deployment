(()=>{let e={unknown:{en:"Unknown Error",zh:"未知错误"},ready:{en:"Ready Into The Website",zh:"即将进入网站"},pending:{en:"You Are Now In Line",zh:"在线人数过多，排队中"},full:{en:"Too Many People Online",zh:"在线人数过多，排队已满"},"order-1":{en:"You Are",zh:"第"},"order-2":{en:"th /",zh:"位 / 共"},"order-3":{en:"People Totally",zh:"位"},"connection-error":{en:"Network Connection Error",zh:"网络连接发生错误，请刷新重试"},"connection-close":{en:"Network Connection Closed",zh:"网络连接意外中断，请刷新重试"},"invalid-data":{en:"Invalid data received",zh:"接收到了不合法的数据，请刷新重试"}};function n(n){let o=e[n];for(language in void 0===o&&(o=e.unknown),o)if(navigator.language.startsWith(language))return o[language];return o.en}function o(e,n){let o=document.createElement("div");return e&&(o.id=e),n&&(o.innerHTML=n),o}function t(e,n,o,l=""){null===e&&(e=document.getElementById(l)),e&&(e[n]=o)}function l(e,n,o,t=""){null===e&&(e=document.getElementById(t)),e&&(e.style[n]=o)}function r(e){t(null,"innerText",n(e),"sl-text")}function d(e){l(null,"display","none","sl-loader"),l(null,"display","none","sl-spin"),l(null,"display","none","sl-order"),t(null,"innerText",n(e),"sl-text")}function s(e,n){t(null,"innerText",e,"sl-order-me"),t(null,"innerText",n,"sl-order-total")}window.SafeLineWaitingRoom=function(){var e;getComputedStyle(document.documentElement).getPropertyValue("--primary-color")||(document.documentElement.style.setProperty("--primary-color","#39f"),document.documentElement.style.setProperty("--light-primary-color","#39f4"),document.documentElement.style.setProperty("--font-color","#fff"),document.documentElement.style.setProperty("--light-font-color","#ffffffb3"),document.documentElement.style.setProperty("--success-color","#68d8a3"),document.documentElement.style.setProperty("--warning-color","#ed5554"),document.documentElement.style.setProperty("--warning-font-color","#fff"),document.documentElement.style.setProperty("--warning-light-font-color","#ffffffb3")),(e=document.createElement("link")).rel="stylesheet",e.type="text/css",e.href="/.safeline/static/waiting.css",document.head.appendChild(e),document.body.appendChild(o("sl-bg"));let l=o("sl-box",`
<div id="sl-animation">
  <div id="sl-loader">
    <div class="sl-loader-dot"></div>
    <div class="sl-loader-dot"></div>
    <div class="sl-loader-dot"></div>
    <div class="sl-loader-dot"></div>
    <div class="sl-loader-dot"></div>
    <div class="sl-loader-dot"></div>
    <div class="sl-loader-dot"></div>
    <div class="sl-loader-dot"></div>
  </div>
</div>
<div id="sl-desc">
  <div id="sl-text"></div>
  <div id="sl-spin">
    <span class="sl-dot">.</span>
    <span class="sl-dot">.</span>
    <span class="sl-dot">.</span>
  </div>
</div>
<div id="sl-status">
  <div id="sl-order">
    <span id="sl-order-1"></span><span id="sl-order-me">-</span><span id="sl-order-2"></span><span id="sl-order-total">-</span><span id="sl-order-3"></span>
  </div>
</div>
`);document.body.appendChild(l),r("pending"),t(null,"innerText",n("order-1"),"sl-order-1"),t(null,"innerText",n("order-2"),"sl-order-2"),t(null,"innerText",n("order-3"),"sl-order-3"),function(){if("full"===function(e){let n=document.cookie.split(";");for(let o=0;o<n.length;o++){let t=n[o].trim();if(t.startsWith(e+"="))return t.substring(e.length+1)}return null}("sl-waiting-state"))return d("full");let e=!1,n=new WebSocket(("https:"===window.location.protocol?"wss://":"ws://")+window.location.host+"/.safeline/api/waiting/ws");n.addEventListener("open",n=>{e=!0}),n.addEventListener("message",n=>{let o=JSON.parse(n.data);o&&"number"==typeof o.pos&&"number"==typeof o.total?(s(o.pos,o.total),0===o.pos&&(e=!1,r("ready"),setTimeout(()=>{location.reload()},3e3))):d("invalid-data")}),n.addEventListener("error",n=>{e&&d("connection-error")}),n.addEventListener("close",n=>{e?d("connection-close"):function e(){fetch("/.safeline/api/waiting/query").then(e=>{if(200===e.status)return e.json();d("connection-error")}).then(n=>{n.err?(console.log(n),d("connection-error")):(s(n.data.pos,n.data.total),0===n.data.pos?(r("ready"),setTimeout(()=>{location.reload()},3e3)):setTimeout(()=>{e()},3e3))}).catch(e=>{console.log(e),d("connection-error")})}()})}()},window.onerror=(e,n,o,t,l)=>{d("unknown"),console.log("message:",e),console.log("source:",n),console.log("position",o,t)}})();