const TITLES={status:"상태",sound:"사운드 및 설정",equalizer:"이퀄라이저",about:"정보 및 디버그"};
const WORDS={noise_cancelling:"노이즈 캔슬링",ambient_sound:"주변 소리",sound_quality:"음질 우선",stable_connection:"연결 우선",worn:"착용 중",wearing:"착용 중",not_wearing:"미착용",not_worn:"미착용",left_not_worn:"왼쪽 미착용",right_not_worn:"오른쪽 미착용",invalid:"상태 확인 불가",when_removed:"착용 해제 시",disabled:"사용 안 함",english:"영어",japanese:"일본어",korean:"한국어",chinese:"중국어",auto:"자동",off:"꺼짐",on:"켜짐"};
const DEBUG_RAW_KEYS=["protocol","support_functions","table2_support_functions","call_mic_control","headset_auto_switch","le_audio_status","le_audio_compatibility"];

export function createState(initial={}){return{theme:"light",readOnly:false,disclaimerAccepted:false,unlocked:false,masked:true,pendingKey:null,savedDevices:[],mac:"",channel:null,connection:{state:"idle",message:""},features:{},lastSync:null,...initial}}
export function reduceState(state,action){
  if(action.type==="initial")return{...state,...action.payload};
  if(action.type==="connection")return{...state,connection:action.payload};
  if(action.type==="feature")return{...state,features:{...state.features,[action.payload.key]:action.payload}};
  if(action.type==="devices")return{...state,savedDevices:action.payload};
  if(action.type==="finished")return{...state,lastSync:new Date()};
  return state;
}
function humanWord(value){return WORDS[value]||String(value).replaceAll("_"," ")}
export function valueLabel(value){
  if(value===null||value===undefined||value==="")return "확인 중";
  if(typeof value==="boolean")return value?"켜짐":"꺼짐";
  if(typeof value==="number")return String(value);
  if(typeof value==="string")return humanWord(value);
  if(Array.isArray(value))return value.join(" · ");
  if("level" in value)return `${value.level}%`;
  if("language" in value)return `${value.enabled?"켜짐":"꺼짐"} · ${humanWord(value.language)}`;
  if("mode" in value)return value.enabled===false?"꺼짐":humanWord(value.mode);
  if("enabled" in value)return value.enabled?"켜짐":"꺼짐";
  return Object.entries(value).map(([key,item])=>`${humanWord(key)} ${valueLabel(item)}`).join(" · ");
}
export function supportLabel(value){return value===null||value===undefined?"확인 중":value?"지원됨":"미지원"}
function parse(payload){try{return JSON.parse(payload)}catch{return{}}}
function currentValue(key){const item=state.features[key];return !item||item.error||item.supported===false?null:item.value}
function canWrite(key){
  if(!state.disclaimerAccepted||!state.unlocked||state.features[key]?.writable!==true)return false;
  if(key==="noise_control")return currentValue("wearing_status")==="worn";
  return true;
}
function isPending(key){return state.pendingKey===key}
function isLocked(key){return !canWrite(key)||isPending(key)}
let state=createState(),bridge=null,toastTimer,pollTimer=null,activePoll=null,lastWearing=null;
const debugHistory={battery:[],ambient:[]};
const POLL_INTERVALS={debug:3000,quick:2500};

function setTheme(theme,persist=true){theme=theme==="dark"?"dark":"light";state={...state,theme};document.documentElement.dataset.theme=theme;const use=document.querySelector("[data-theme-toggle] use");if(use)use.setAttribute("href",`assets/lucide.svg#${theme==="dark"?"moon":"sun"}`);if(persist)bridge?.saveTheme(theme)}
function showToast(message){const node=document.querySelector("[data-toast]");node.textContent=message;node.classList.add("visible");clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.classList.remove("visible"),3200)}
// Two background polls share one scheduler: "quick" (wearing status + battery,
// runs on every view once connected, cheap) and "debug" (the full debug-panel
// key set, only while that tab is open -- it's a superset so it supersedes
// "quick" rather than running alongside it). Each re-request waits for the
// previous one's refreshFinished before scheduling the next, so a slow
// Bluetooth round-trip never piles up overlapping requests.
function requestPoll(kind){if(kind==="debug")bridge?.requestDebugState();else if(kind==="quick")bridge?.requestQuickState()}
function setActivePoll(kind){if(activePoll===kind)return;activePoll=kind;clearTimeout(pollTimer);pollTimer=null;if(kind)requestPoll(kind)}
let currentView="status",currentSubtab="info";
function pollTargetForView(){return currentView==="about"&&currentSubtab==="debug"?"debug":"quick"}
function setView(view){currentView=view;document.querySelectorAll("[data-view-panel]").forEach(n=>n.classList.toggle("active",n.dataset.viewPanel===view));document.querySelectorAll(".sidebar [data-view]").forEach(n=>n.classList.toggle("active",n.dataset.view===view));document.querySelector("[data-view-title]").textContent=TITLES[view]||view;setActivePoll(pollTargetForView())}
function setSubtab(name){currentSubtab=name;document.querySelectorAll("[data-subview]").forEach(n=>n.classList.toggle("active",n.dataset.subview===name));document.querySelectorAll("[data-subtab]").forEach(n=>n.classList.toggle("active",n.dataset.subtab===name));setActivePoll(pollTargetForView())}
function write(key,value){if(!canWrite(key)){showToast(state.unlocked?"이 설정은 현재 변경할 수 없습니다.":"먼저 상단의 잠금을 해제해 주세요.");render();return}state={...state,pendingKey:key};render();bridge?.setFeature(key,JSON.stringify(value))}
function populateDevices(){const select=document.querySelector("[data-device-select]");select.replaceChildren(new Option("직접 입력",""));state.savedDevices.forEach((item,index)=>select.add(new Option(`${item.name} · ${item.mac}`,String(index))))}
function setUnlocked(value){state={...state,unlocked:value};render()}

export function sparklinePoints(values,max){
  if(values.length<2)return"";
  const width=200,height=60,step=width/(values.length-1);
  return values.map((value,index)=>`${(index*step).toFixed(1)},${(height-Math.min(1,value/max)*height).toFixed(1)}`).join(" ");
}
export function pushHistory(list,value){if(typeof value!=="number")return;if(list.length&&list[list.length-1]===value)return;list.push(value);if(list.length>40)list.shift()}
function renderDebug(){
  const battery=currentValue("battery");
  if(battery&&typeof battery.level==="number"){
    pushHistory(debugHistory.battery,battery.level);
    document.querySelector('[data-debug-value="battery"]').textContent=`${battery.level}%${battery.charging?" · 충전 중":""}`;
  }
  const noise=currentValue("noise_control");
  if(noise&&typeof noise.ambient_level==="number"){
    pushHistory(debugHistory.ambient,noise.ambient_level);
    document.querySelector('[data-debug-value="ambient"]').textContent=String(noise.ambient_level);
  }
  document.querySelector('[data-sparkline="battery"] polyline').setAttribute("points",sparklinePoints(debugHistory.battery,100));
  document.querySelector('[data-sparkline="ambient"] polyline').setAttribute("points",sparklinePoints(debugHistory.ambient,20));
  const wearing=currentValue("wearing_status");
  if(wearing!==null&&wearing!==lastWearing){
    lastWearing=wearing;
    const list=document.querySelector("[data-wearing-timeline]"),item=document.createElement("li");
    const stamp=new Date().toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit",second:"2-digit"});
    item.textContent=`${stamp} · ${valueLabel(wearing)}`;
    list.prepend(item);
    while(list.children.length>8)list.removeChild(list.lastChild);
  }
  const tbody=document.querySelector("[data-debug-table]");
  tbody.replaceChildren(...DEBUG_RAW_KEYS.map(key=>{
    const item=state.features[key],tr=document.createElement("tr");
    const cells=[item?.label||key,item&&!item.error?valueLabel(item.value):"확인 중",item?.raw||"—"];
    cells.forEach((text,index)=>{const td=document.createElement("td");td.textContent=text;if(index===2)td.className="mono";tr.append(td)});
    return tr;
  }));
  if(battery||noise||wearing!==null){
    document.querySelector("[data-debug-sync]").textContent=`마지막 갱신 ${new Date().toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit",second:"2-digit"})}`;
  }
}

function render(){
  document.querySelectorAll("[data-feature]").forEach(node=>node.textContent=valueLabel(currentValue(node.dataset.feature)));
  document.querySelectorAll("[data-support]").forEach(node=>node.textContent=supportLabel(currentValue(node.dataset.support)));
  document.querySelector("[data-device-address]").textContent=state.mac||"기기 미선택";
  document.querySelector("[data-current-mac]").textContent=state.masked?"••:••:••:••:••:••":(state.mac||"—");
  document.querySelector("[data-current-channel]").textContent=state.masked?"••":(state.channel??"—");
  document.querySelector("[data-mask-toggle]").classList.toggle("revealed",!state.masked);
  const status=state.connection.state,label=status==="connected"?"연결됨":status==="connecting"?"연결 중":status==="failed"?"연결 실패":"연결 대기";document.querySelector("[data-side-status]").textContent=label;document.querySelector("[data-connection-label]").textContent=label;document.querySelectorAll("[data-status-dot],.connection-label i").forEach(n=>{n.classList.toggle("online",status==="connected");n.classList.toggle("busy",status==="connecting")});
  if(state.lastSync)document.querySelector("[data-sync-time]").textContent=`마지막 동기화 ${state.lastSync.toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"})}`;
  const battery=currentValue("battery");
  if(battery&&typeof battery.level==="number"){
    document.querySelector("[data-battery-fill]").style.width=`${Math.min(100,battery.level)}%`;
    document.querySelector("[data-battery-meter]").title=`배터리 잔량 게이지 · ${battery.level}%`;
  }
  document.querySelector("[data-wear-dot]").classList.toggle("on",currentValue("wearing_status")==="worn");
  const noise=currentValue("noise_control"),wornForNoise=currentValue("wearing_status")==="worn",noiseLocked=isLocked("noise_control");
  const statusNoiseMode=document.querySelector("[data-status-noise-mode]"),statusNoiseFill=document.querySelector("[data-status-noise-fill]");
  if(statusNoiseMode)statusNoiseMode.textContent=noise?valueLabel(noise):"확인 중";
  const statusNoiseLevel=document.querySelector("[data-status-noise-level]"),statusNoiseMeter=document.querySelector("[data-status-noise-meter]");
  if(statusNoiseFill&&noise?.ambient_level!==undefined){
    // ambient_level is only meaningful while noise control is actually enabled --
    // showing a filled gauge next to "꺼짐" reads as a bug, not "off at level N".
    const active=noise.enabled!==false;
    statusNoiseFill.style.width=active?`${Math.min(100,(noise.ambient_level/20)*100)}%`:"0%";
    if(statusNoiseLevel)statusNoiseLevel.textContent=active?`${noise.ambient_level}/20`:"꺼짐";
    if(statusNoiseMeter)statusNoiseMeter.title=active?`주변 소리 레벨 게이지 · ${noise.ambient_level}/20`:"노이즈 제어가 꺼져 있어 레벨이 적용되지 않습니다";
  }
  document.querySelector("[data-noise-lock-note]").classList.toggle("hidden",wornForNoise);
  document.querySelectorAll("[data-lock-note]").forEach(n=>n.classList.toggle("hidden",state.unlocked));
  const noiseHint=document.querySelector("[data-noise-hint]");
  if(noiseHint)noiseHint.textContent=noise?`${valueLabel(noise)}${wornForNoise?"":" (착용 시 실제 설정으로 갱신)"}${isPending("noise_control")?" · 적용 중…":""}`:"확인 중";
  const noiseModeSelect=document.querySelector("[data-noise-mode-select]");
  if(noiseModeSelect){noiseModeSelect.disabled=noiseLocked;if(noise?.mode)noiseModeSelect.value=noise.mode}
  const noiseLevelRange=document.querySelector("[data-noise-level-range]"),noiseLevelOutput=document.querySelector("[data-noise-level-output]");
  if(noiseLevelRange){noiseLevelRange.disabled=noiseLocked;if(noise?.ambient_level!==undefined)noiseLevelRange.value=noise.ambient_level}
  if(noiseLevelOutput)noiseLevelOutput.textContent=noise?.ambient_level!==undefined?String(noise.ambient_level):"—";
  document.querySelectorAll("[data-toggle]").forEach(input=>{const key=input.dataset.toggle,value=currentValue(key);input.disabled=isLocked(key);input.checked=key==="auto_power_off"?value?.mode==="when_removed":Boolean(value?.enabled??value)});
  document.querySelectorAll("[data-select]").forEach(input=>{input.disabled=isLocked(input.dataset.select);const value=currentValue(input.dataset.select);if(value!==null)input.value=value});
  document.querySelectorAll("[data-range]").forEach(input=>{input.disabled=isLocked(input.dataset.range);const value=currentValue(input.dataset.range);if(value!==null)input.value=value});
  const eq=currentValue("equalizer");
  if(eq&&typeof eq==="object"){
    document.querySelector("[data-eq-preset]").textContent=`프리셋 ${eq.preset}${isPending("equalizer")?" · 적용 중…":""}`;
    document.querySelectorAll("[data-eq-band]").forEach((input,index)=>{const value=eq.bands?.[index]??10;input.value=value;input.style.setProperty("--fill",`${(value/20)*100}%`);input.disabled=isLocked("equalizer")});
  }
  const badge=document.querySelector("[data-unlock-toggle]"),badgeLabel=document.querySelector("[data-unlock-label]"),badgeIcon=document.querySelector("[data-unlock-icon] use");
  if(badge){badge.classList.toggle("unlocked",state.unlocked);if(badgeLabel)badgeLabel.textContent=state.unlocked?"잠금 해제됨 · 직접 쓰기 가능":"검증된 설정만 쓰기";if(badgeIcon)badgeIcon.setAttribute("href",`assets/lucide.svg#${state.unlocked?"shield-check":"lock"}`)}
  document.querySelector("[data-disclaimer]").classList.toggle("hidden",state.disclaimerAccepted);populateDevices();
  renderDebug();
}
function dispatch(action){state=reduceState(state,action);render()}
function attachBridge(candidate){bridge=candidate;bridge.initialState.connect(payload=>{const initial=parse(payload);dispatch({type:"initial",payload:initial});setTheme(initial.theme,false);const form=document.querySelector("[data-connect-form]");if(initial.mac)form.elements.mac.value=initial.mac;if(initial.channel)form.elements.channel.value=initial.channel;if(initial.disclaimerAccepted){document.querySelector("[data-connect-overlay]").classList.remove("hidden");bridge.requestDevices();if(initial.mac&&initial.channel)bridge.refresh()}});bridge.connectionState.connect(payload=>{const connection=parse(payload);dispatch({type:"connection",payload:connection});if(connection.state==="connected"||connection.state==="connecting")document.querySelector("[data-connect-overlay]").classList.add("hidden");if(connection.state==="failed"&&connection.message)showToast(connection.message);if(connection.state==="connected")setActivePoll(pollTargetForView());if(connection.state==="failed")setActivePoll(null)});bridge.featureState.connect(payload=>dispatch({type:"feature",payload:parse(payload)}));bridge.devicesState.connect(payload=>dispatch({type:"devices",payload:parse(payload)}));bridge.refreshFinished.connect(()=>{state={...state,pendingKey:null};dispatch({type:"finished"});if(activePoll){clearTimeout(pollTimer);pollTimer=setTimeout(()=>requestPoll(activePoll),POLL_INTERVALS[activePoll])}});bridge.userMessage.connect(showToast);bridge.requestInitialState()}
function setup(){
  const bars=document.querySelector("[data-eq-bars]");for(let i=0;i<10;i++){const wrap=document.createElement("label");wrap.className="eq-band";const input=document.createElement("input");input.type="range";input.min="0";input.max="20";input.dataset.eqBand=String(i);input.style.setProperty("--fill","50%");input.addEventListener("input",()=>input.style.setProperty("--fill",`${(Number(input.value)/20)*100}%`));input.addEventListener("change",()=>{const eq=currentValue("equalizer");if(!eq)return;const bands=[...eq.bands];bands[i]=Number(input.value);write("equalizer",{...eq,bands})});wrap.append(input);bars.append(wrap)}
  document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
  document.querySelectorAll("[data-subtab]").forEach(button=>button.addEventListener("click",()=>setSubtab(button.dataset.subtab)));document.querySelector("[data-theme-toggle]").addEventListener("click",()=>setTheme(state.theme==="dark"?"light":"dark"));document.querySelector("[data-refresh]").addEventListener("click",()=>bridge?.refresh());
  document.querySelectorAll("[data-toggle]").forEach(input=>input.addEventListener("change",()=>{const key=input.dataset.toggle,current=currentValue(key);let value=input.checked;if(key==="speak_to_chat")value={...current,enabled:input.checked};if(key==="auto_power_off")value={...current,mode:input.checked?"when_removed":"disabled"};if(key==="voice_guidance")value={...current,enabled:input.checked};write(key,value)}));document.querySelectorAll("[data-select]").forEach(input=>input.addEventListener("change",()=>write(input.dataset.select,input.value)));document.querySelectorAll("[data-range]").forEach(input=>input.addEventListener("change",()=>write(input.dataset.range,Number(input.value))));
  document.querySelector("[data-noise-mode-select]").addEventListener("change",event=>{const current=currentValue("noise_control");if(!current)return;write("noise_control",{...current,mode:event.target.value})});
  document.querySelector("[data-noise-level-range]").addEventListener("change",event=>{const current=currentValue("noise_control");if(!current)return;write("noise_control",{...current,ambient_level:Number(event.target.value)})});
  document.querySelector("[data-mask-toggle]").addEventListener("click",()=>{state={...state,masked:!state.masked};render()});
  document.querySelector("[data-disclaimer-accept]").addEventListener("click",()=>{state={...state,disclaimerAccepted:true};bridge?.acceptDisclaimer();render();document.querySelector("[data-connect-overlay]").classList.remove("hidden");bridge?.requestDevices()});document.querySelector("[data-disclaimer-reject]").addEventListener("click",()=>bridge?.rejectDisclaimer());document.querySelector("[data-scan]").addEventListener("click",()=>bridge?.requestDevices());document.querySelector("[data-device-select]").addEventListener("change",event=>{const item=state.savedDevices[Number(event.target.value)];if(item){const form=document.querySelector("[data-connect-form]");form.elements.mac.value=item.mac;form.elements.channel.value=item.channel}});
  document.querySelector("[data-connect-form]").addEventListener("submit",event=>{event.preventDefault();const data=new FormData(event.currentTarget),mac=String(data.get("mac")),channel=Number(data.get("channel")),selected=String(data.get("saved")),item=selected===""?null:state.savedDevices[Number(selected)];if(bridge)bridge.connectNamedDevice(mac,channel,item?.name||"WH-1000XM6")});
  document.querySelector("[data-unlock-toggle]").addEventListener("click",()=>{
    if(state.unlocked){setUnlocked(false);return}
    const checkbox=document.querySelector("[data-unlock-checkbox]"),confirmButton=document.querySelector("[data-unlock-confirm]");
    checkbox.checked=false;confirmButton.disabled=true;
    document.querySelector("[data-unlock-overlay]").classList.remove("hidden");
  });
  document.querySelector("[data-unlock-checkbox]").addEventListener("change",event=>{document.querySelector("[data-unlock-confirm]").disabled=!event.target.checked});
  document.querySelector("[data-unlock-cancel]").addEventListener("click",()=>document.querySelector("[data-unlock-overlay]").classList.add("hidden"));
  document.querySelector("[data-unlock-confirm]").addEventListener("click",()=>{document.querySelector("[data-unlock-overlay]").classList.add("hidden");setUnlocked(true)});
  setTheme("light",false);if(window.qt?.webChannelTransport&&window.QWebChannel)new QWebChannel(window.qt.webChannelTransport,channel=>attachBridge(channel.objects.sonusBridge));
}
if(typeof document!=="undefined"){if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",setup,{once:true});else setup()}
