const fs=require('node:fs');
const assert=require('node:assert/strict');
const vm=require('node:vm');

const code=fs.readFileSync('embed-host.js','utf8');
new vm.Script(code,{filename:'embed-host.js'});

function element(initial={}) {
 const attrs={...initial};
 return {
  style:{scrollBehavior:''},
  getAttribute:name=>Object.prototype.hasOwnProperty.call(attrs,name)?attrs[name]:null,
  setAttribute(name,value){attrs[name]=String(value);},
  removeAttribute(name){delete attrs[name];}
 };
}

const html=element({style:'scroll-behavior:smooth'});
const body=element({style:'background:#fff'});
const frame=element({style:'width:100%;height:650px'});
const childMessages=[];
frame.src='https://leffernan.github.io/bygdebladet-lokalfotball/';
frame.contentWindow={postMessage:(message,origin)=>childMessages.push({message,origin})};
frame.showPopover=function(){
 assert.equal(this.getAttribute('popover'),'manual');
 this.popoverVisible=true;
};
frame.hidePopover=function(){this.popoverVisible=false;};

const handlers={};
let restored=null;
const context=vm.createContext({
 URL,
 location:{href:'https://www.bygdebladet.com/lokalfotball'},
 document:{body,documentElement:html,querySelectorAll:selector=>selector==='iframe'?[frame]:[]},
 window:{
  scrollY:385,
  addEventListener:(type,handler)=>{handlers[type]=handler;},
  scrollTo:(x,y)=>{restored=[x,y];}
 }
});
vm.runInContext(code,context);

function message(type,origin='https://leffernan.github.io'){
 handlers.message({
  origin,
  source:frame.contentWindow,
  data:{source:'bygdebladet-lokalfotball-v1',type}
 });
}
message('match-open','https://other.example');
assert.equal(frame.popoverVisible,undefined,'Untrusted origins must be ignored');
message('match-open');
assert.equal(frame.popoverVisible,true,'Existing iframe must enter the browser top layer');
assert.equal(frame.style.position,'fixed');
assert.equal(frame.style.height,'100dvh','Expanded iframe must fill the viewport');
assert.equal(frame.style.inset,'0');
assert.equal(frame.style.padding,'0');
assert.equal(body.style.position,'fixed','Newspaper background must stay still');
assert.equal(childMessages.length,1,'Child must receive activation signal');
assert.equal(childMessages[0].message.type,'match-activated');
assert.equal(childMessages[0].origin,'https://leffernan.github.io');
message('match-close');
assert.equal(frame.popoverVisible,false,'Popover must be hidden after match closes');
assert.equal(frame.getAttribute('popover'),null,'Temporary popover attribute must be removed');
assert.equal(frame.getAttribute('style'),'width:100%;height:650px','Original iframe style must be restored');
assert.equal(body.getAttribute('style'),'background:#fff','Newspaper body style must be restored');
assert.equal(html.getAttribute('style'),'scroll-behavior:smooth','Newspaper document style must be restored');
assert.deepEqual(restored,[0,385],'Newspaper scroll position must be restored');
message('match-open');
assert.equal(frame.popoverVisible,true,'The same iframe should reopen without reloading');
message('match-close');

console.log('Iframe top-layer and restore checks passed.');
