const TITLES={status:"상태",sound:"사운드",equalizer:"이퀄라이저",device:"기기 설정",about:"정보"};
const WORDS={noise_cancelling:"노이즈 캔슬링",ambient_sound:"주변 소리",sound_quality:"음질 우선",stable_connection:"연결 우선",wearing:"착용 중",not_wearing:"미착용",not_worn:"미착용",when_removed:"착용 해제 시",disabled:"사용 안 함",english:"영어",japanese:"일본어",korean:"한국어",chinese:"중국어",auto:"자동",off:"꺼짐",on:"켜짐"};

export function createState(initial={}){return{theme:"light",readOnly:false,disclaimerAccepted:false,savedDevices:[],mac:"",channel:null,connection:{state:"idle",message:""},features:{},lastSync:null,...initial}}
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
function parse(payload){try{return JSON.parse(payload)}catch{return{}}}
function currentValue(key){const item=state.features[key];return !item||item.error||item.supported===false?null:item.value}
function canWrite(key){return state.disclaimerAccepted&&state.features[key]?.writable===true}
let state=createState(),bridge=null,toastTimer;

function setTheme(theme,persist=true){theme=theme==="dark"?"dark":"light";state={...state,theme};document.documentElement.dataset.theme=theme;const use=document.querySelector("[data-theme-toggle] use");if(use)use.setAttribute("href",`assets/lucide.svg#${theme==="dark"?"moon":"sun"}`);if(persist)bridge?.saveTheme(theme)}
function showToast(message){const node=document.querySelector("[data-toast]");node.textContent=message;node.classList.add("visible");clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.classList.remove("visible"),3200)}
function setView(view){document.querySelectorAll("[data-view-panel]").forEach(n=>n.classList.toggle("active",n.dataset.viewPanel===view));document.querySelectorAll(".sidebar [data-view]").forEach(n=>n.classList.toggle("active",n.dataset.view===view));document.querySelector("[data-view-title]").textContent=TITLES[view]||view}
function write(key,value){if(!canWrite(key)){showToast("이 설정은 현재 변경할 수 없습니다.");render();return}bridge?.setFeature(key,JSON.stringify(value))}
function populateDevices(){const select=document.querySelector("[data-device-select]");select.replaceChildren(new Option("직접 입력",""));state.savedDevices.forEach((item,index)=>select.add(new Option(`${item.name} · ${item.mac}`,String(index))))}
function render(){
  document.querySelectorAll("[data-feature]").forEach(node=>node.textContent=valueLabel(currentValue(node.dataset.feature)));
  document.querySelector("[data-device-address]").textContent=state.mac||"기기 미선택";document.querySelector("[data-current-mac]").textContent=state.mac||"—";document.querySelector("[data-current-channel]").textContent=state.channel??"—";
  const status=state.connection.state,label=status==="connected"?"연결됨":status==="connecting"?"연결 중":status==="failed"?"연결 실패":"연결 대기";document.querySelector("[data-side-status]").textContent=label;document.querySelector("[data-connection-label]").textContent=label;document.querySelectorAll("[data-status-dot],.connection-label i").forEach(n=>{n.classList.toggle("online",status==="connected");n.classList.toggle("busy",status==="connecting")});
  if(state.lastSync)document.querySelector("[data-sync-time]").textContent=`마지막 동기화 ${state.lastSync.toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"})}`;
  const noise=currentValue("noise_control"),detail=document.querySelector('[data-detail="noise_control"]');if(noise&&detail)detail.textContent=`${valueLabel(noise)}${noise.ambient_level!==undefined?` · 주변 소리 ${noise.ambient_level}`:""}`;
  document.querySelectorAll("[data-toggle]").forEach(input=>{const key=input.dataset.toggle,value=currentValue(key);input.disabled=!canWrite(key);input.checked=key==="auto_power_off"?value?.mode==="when_removed":Boolean(value?.enabled??value)});
  document.querySelectorAll("[data-select]").forEach(input=>{input.disabled=!canWrite(input.dataset.select);const value=currentValue(input.dataset.select);if(value!==null)input.value=value});
  document.querySelectorAll("[data-range]").forEach(input=>{input.disabled=!canWrite(input.dataset.range);const value=currentValue(input.dataset.range);if(value!==null)input.value=value});
  const eq=currentValue("equalizer");if(eq&&typeof eq==="object"){document.querySelector("[data-eq-preset]").textContent=`프리셋 ${eq.preset}`;document.querySelectorAll("[data-eq-band]").forEach((input,index)=>{input.value=eq.bands?.[index]??10;input.disabled=!canWrite("equalizer")})}
  document.querySelector("[data-disclaimer]").classList.toggle("hidden",state.disclaimerAccepted);populateDevices();
}
function dispatch(action){state=reduceState(state,action);render()}
function attachBridge(candidate){bridge=candidate;bridge.initialState.connect(payload=>{const initial=parse(payload);dispatch({type:"initial",payload:initial});setTheme(initial.theme,false);const form=document.querySelector("[data-connect-form]");if(initial.mac)form.elements.mac.value=initial.mac;if(initial.channel)form.elements.channel.value=initial.channel;if(initial.disclaimerAccepted){document.querySelector("[data-connect-overlay]").classList.remove("hidden");bridge.requestDevices();if(initial.mac&&initial.channel)bridge.refresh()}});bridge.connectionState.connect(payload=>{const connection=parse(payload);dispatch({type:"connection",payload:connection});if(connection.state==="connected"||connection.state==="connecting")document.querySelector("[data-connect-overlay]").classList.add("hidden");if(connection.state==="failed"&&connection.message)showToast(connection.message)});bridge.featureState.connect(payload=>dispatch({type:"feature",payload:parse(payload)}));bridge.devicesState.connect(payload=>dispatch({type:"devices",payload:parse(payload)}));bridge.refreshFinished.connect(()=>dispatch({type:"finished"}));bridge.userMessage.connect(showToast);bridge.requestInitialState()}
function setup(){
  const bars=document.querySelector("[data-eq-bars]");for(let i=0;i<10;i++){const wrap=document.createElement("label");wrap.className="eq-band";const input=document.createElement("input");input.type="range";input.min="0";input.max="20";input.dataset.eqBand=String(i);input.addEventListener("change",()=>{const eq=currentValue("equalizer");if(!eq)return;const bands=[...eq.bands];bands[i]=Number(input.value);write("equalizer",{...eq,bands})});wrap.append(input);bars.append(wrap)}
  document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));document.querySelector("[data-theme-toggle]").addEventListener("click",()=>setTheme(state.theme==="dark"?"light":"dark"));document.querySelector("[data-refresh]").addEventListener("click",()=>bridge?.refresh());
  document.querySelectorAll("[data-toggle]").forEach(input=>input.addEventListener("change",()=>{const key=input.dataset.toggle,current=currentValue(key);let value=input.checked;if(key==="speak_to_chat")value={...current,enabled:input.checked};if(key==="auto_power_off")value={...current,mode:input.checked?"when_removed":"disabled"};if(key==="voice_guidance")value={...current,enabled:input.checked};write(key,value)}));document.querySelectorAll("[data-select]").forEach(input=>input.addEventListener("change",()=>write(input.dataset.select,input.value)));document.querySelectorAll("[data-range]").forEach(input=>input.addEventListener("change",()=>write(input.dataset.range,Number(input.value))));
  document.querySelector("[data-disclaimer-accept]").addEventListener("click",()=>{state={...state,disclaimerAccepted:true};bridge?.acceptDisclaimer();render();document.querySelector("[data-connect-overlay]").classList.remove("hidden");bridge?.requestDevices()});document.querySelector("[data-disclaimer-reject]").addEventListener("click",()=>bridge?.rejectDisclaimer());document.querySelector("[data-scan]").addEventListener("click",()=>bridge?.requestDevices());document.querySelector("[data-device-select]").addEventListener("change",event=>{const item=state.savedDevices[Number(event.target.value)];if(item){const form=document.querySelector("[data-connect-form]");form.elements.mac.value=item.mac;form.elements.channel.value=item.channel}});
  document.querySelector("[data-connect-form]").addEventListener("submit",event=>{event.preventDefault();const data=new FormData(event.currentTarget),mac=String(data.get("mac")),channel=Number(data.get("channel")),selected=String(data.get("saved")),item=selected===""?null:state.savedDevices[Number(selected)];if(bridge)bridge.connectNamedDevice(mac,channel,item?.name||"WH-1000XM6")});
  setTheme("light",false);if(window.qt?.webChannelTransport&&window.QWebChannel)new QWebChannel(window.qt.webChannelTransport,channel=>attachBridge(channel.objects.sonusBridge));
}
if(typeof document!=="undefined"){if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",setup,{once:true});else setup()}
