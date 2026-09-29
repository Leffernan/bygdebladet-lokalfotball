/* Add this script to the newspaper page that contains the Lokalfotball iframe.
   It never accesses the iframe document: communication is via checked postMessage events. */
(()=>{
 'use strict';
 if(window.__bygdebladetLokalfotballEmbed)return;
 window.__bygdebladetLokalfotballEmbed=true;
 const ORIGIN='https://leffernan.github.io';
 const PATH='/bygdebladet-lokalfotball/';
 const SOURCE='bygdebladet-lokalfotball-v1';
 let active=null;
 const originalStyle=element=>element.getAttribute('style');
 function restoreStyle(element,value){
   if(value===null)element.removeAttribute('style');
   else element.setAttribute('style',value);
 }
 function findFrame(sourceWindow){
   return [...document.querySelectorAll('iframe[src]')].find(frame=>{
     if(frame.contentWindow!==sourceWindow)return false;
     try{
       const url=new URL(frame.src,document.baseURI);
       return url.origin===ORIGIN && (url.pathname===PATH.slice(0,-1)||url.pathname.startsWith(PATH));
     }catch{return false}
   });
 }
 function lock(frame){
   if(active)return;
   const root=document.documentElement,body=document.body,scrollY=window.scrollY;
   const ancestors=[];
   // CMS wrappers can clip or establish a containing block for a fixed iframe.
   for(let element=frame.parentElement;element&&element!==body&&element!==root;element=element.parentElement){
     ancestors.push({element,style:originalStyle(element)});
     for(const [name,value] of Object.entries({
       overflow:'visible',transform:'none',perspective:'none',filter:'none',
       'backdrop-filter':'none',contain:'none','will-change':'auto',
       'clip-path':'none',position:'relative','z-index':'2147483646'
     }))element.style.setProperty(name,value,'important');
   }
   active={frame,root,body,scrollY,ancestors,frameStyle:originalStyle(frame),rootStyle:originalStyle(root),bodyStyle:originalStyle(body)};
   root.style.setProperty('overflow','hidden','important');
   for(const [name,value] of Object.entries({
     position:'fixed',top:`-${scrollY}px`,left:'0',right:'0',width:'100%',overflow:'hidden'
   }))body.style.setProperty(name,value,'important');
   for(const [name,value] of Object.entries({
     position:'fixed',top:'0',left:'0',right:'0',bottom:'0',
     width:'100vw',height:'100vh','max-width':'none','max-height':'none',
     'aspect-ratio':'auto',margin:'0',border:'0',display:'block',
     'z-index':'2147483647'
   }))frame.style.setProperty(name,value,'important');
   if(CSS.supports('height','100dvh'))frame.style.setProperty('height','100dvh','important');
   frame.contentWindow.postMessage({source:SOURCE,type:'match-activated'},ORIGIN);
 }
 function unlock(){
   if(!active)return;
   const {frame,root,body,scrollY,ancestors,frameStyle,rootStyle,bodyStyle}=active;
   active=null;
   restoreStyle(frame,frameStyle);
   for(const item of ancestors.reverse())restoreStyle(item.element,item.style);
   restoreStyle(body,bodyStyle);
   restoreStyle(root,rootStyle);
   const before=root.style.scrollBehavior;
   root.style.scrollBehavior='auto';
   window.scrollTo(0,scrollY);
   root.style.scrollBehavior=before;
 }
 window.addEventListener('message',event=>{
   if(event.origin!==ORIGIN||event.data?.source!==SOURCE)return;
   const frame=findFrame(event.source);
   if(!frame)return;
   if(event.data.type==='match-open')lock(frame);
   else if(event.data.type==='match-close'&&active?.frame===frame)unlock();
 });
 window.addEventListener('pagehide',unlock);
})();
