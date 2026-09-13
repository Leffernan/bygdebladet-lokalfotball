const TARGET_CLUBS = [
  'Vestnes Varfjell','Tomrefjord','Fiksdal/Rekdal','Ørskog','Stordal','Skodje',
  'Brattvåg','Ravn','Norborg','HaNo','Harøy','Lepsøy','Hildre'
];

let allMatches = [];
let selectedPeriod = 'all';
const $ = (s) => document.querySelector(s);
const fmtDate = (iso, opts={}) => new Intl.DateTimeFormat('nn-NO', opts).format(new Date(`${iso}T12:00:00`));

function initials(team){
  return team.split(/[\s/]+/).filter(Boolean).slice(0,3).map(x=>x[0]).join('').toUpperCase();
}
function isLocalName(name){
  const lower = name.toLowerCase();
  return TARGET_CLUBS.some(c => lower.includes(c.toLowerCase()));
}
function dateKey(date){ return date; }
function periodMatch(m){
  if(selectedPeriod==='all') return true;
  const today = new Date();
  today.setHours(12,0,0,0);
  const d = new Date(`${m.date}T12:00:00`);
  const diff = Math.round((today-d)/86400000);
  if(selectedPeriod==='today') return diff===0;
  if(selectedPeriod==='yesterday') return diff===1;
  if(selectedPeriod==='week'){
    const day = (today.getDay()+6)%7;
    const monday = new Date(today); monday.setDate(today.getDate()-day);
    return d>=monday && d<=today;
  }
  return true;
}
function filtered(){
  const age = $('#ageFilter').value;
  const club = $('#clubFilter').value;
  return allMatches.filter(m => periodMatch(m))
    .filter(m => age==='all'||m.age===age)
    .filter(m => club==='all'||m.home.toLowerCase().includes(club.toLowerCase())||m.away.toLowerCase().includes(club.toLowerCase()));
}
function renderHero(){
  const m = allMatches[0];
  if(!m) return;
  const scorers = (m.events||[]).filter(e=>e.type==='goal' && e.team===m.localTeam).slice(0,3);
  $('#heroScore').innerHTML = `
    <article class="featured-card">
      <div class="featured-top"><span>${m.age} · ${m.competition}</span><span class="featured-status">SLUTT</span></div>
      <div class="featured-teams">
        <div class="featured-team"><div class="crest">${initials(m.home)}</div>${m.home}</div>
        <div class="featured-score">${m.homeScore}–${m.awayScore}</div>
        <div class="featured-team"><div class="crest">${initials(m.away)}</div>${m.away}</div>
      </div>
      <div class="featured-meta">${m.halfTime?`${m.halfTime} til pause · `:''}${m.venue} · ${fmtDate(m.date,{weekday:'long',day:'numeric',month:'long'})}</div>
      ${scorers.length?`<div class="featured-scorers">${scorers.map(e=>`<span class="scorer-pill">⚽ ${e.player} ${e.minute}'</span>`).join('')}</div>`:''}
    </article>`;
}
function renderStats(){
  const week = allMatches.filter(m=>{
    const today=new Date(); today.setHours(12,0,0,0); const d=new Date(`${m.date}T12:00:00`); return (today-d)/86400000<=7 && d<=today;
  });
  const goals=week.reduce((s,m)=>s+m.homeScore+m.awayScore,0);
  const teams=new Set(week.flatMap(m=>[m.home,m.away].filter(isLocalName)));
  $('#statsStrip').innerHTML=`<div class="stat"><strong>${week.length}</strong><span>kampar siste 7 dagar</span></div><div class="stat"><strong>${goals}</strong><span>mål totalt</span></div><div class="stat"><strong>${teams.size}</strong><span>lokale lag i aksjon</span></div>`;
}
function renderFilters(){
  [...new Set(allMatches.map(m=>m.age))].sort().forEach(age=>$('#ageFilter').insertAdjacentHTML('beforeend',`<option>${age}</option>`));
  TARGET_CLUBS.forEach(c=>$('#clubFilter').insertAdjacentHTML('beforeend',`<option>${c}</option>`));
}
function card(m){
  return `<article class="match-card" tabindex="0" data-id="${m.id}" role="button" aria-label="Opne ${m.home} mot ${m.away}">
    <div class="match-meta"><div class="competition">${m.age} · ${m.competition}</div><div class="venue">${m.venue}${m.time?` · ${m.time}`:''}</div></div>
    <div class="teams">
      <div class="team-row ${isLocalName(m.home)?'local':''}"><div class="team-name">${m.home}</div><div class="team-score">${m.homeScore}</div></div>
      <div class="team-row ${isLocalName(m.away)?'local':''}"><div class="team-name">${m.away}</div><div class="team-score">${m.awayScore}</div></div>
    </div>
    <div class="match-side"><div class="fulltime">SLUTT</div><div class="halftime">${m.halfTime?`Pause ${m.halfTime}`:'–'}</div><div class="arrow">→</div></div>
  </article>`;
}
function renderMatches(){
  const list=filtered().sort((a,b)=>`${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`));
  $('#emptyState').hidden=list.length>0;
  let html='', last='';
  list.forEach(m=>{
    if(dateKey(m.date)!==last){ last=dateKey(m.date); html+=`<div class="date-heading">${fmtDate(m.date,{weekday:'long',day:'numeric',month:'long',year:'numeric'})}</div>`; }
    html+=card(m);
  });
  $('#matchList').innerHTML=html;
  document.querySelectorAll('.match-card').forEach(el=>{
    el.addEventListener('click',()=>openMatch(el.dataset.id));
    el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openMatch(el.dataset.id)}});
  });
}
function openMatch(id){
  const m=allMatches.find(x=>x.id===id); if(!m)return;
  const localEvents=(m.events||[]).filter(e=>e.team===m.localTeam);
  $('#dialogContent').innerHTML=`
    <div class="dialog-hero">
      <div class="dialog-label">${m.age} · ${m.competition} · SLUTT</div>
      <div class="dialog-score"><div class="dialog-team">${m.home}</div><div class="dialog-result">${m.homeScore}–${m.awayScore}</div><div class="dialog-team">${m.away}</div></div>
      <div class="dialog-facts"><span>${fmtDate(m.date,{weekday:'long',day:'numeric',month:'long'})}</span><span>•</span><span>${m.venue}</span>${m.halfTime?`<span>•</span><span>Pause ${m.halfTime}</span>`:''}</div>
    </div>
    <div class="dialog-body">
      ${localEvents.length?`<section class="detail-section"><h3>LOKALE MÅL</h3><div class="timeline">${localEvents.map(e=>`<div class="event"><div class="event-time">${e.minute}'</div><div class="event-text">⚽ ${e.player}</div></div>`).join('')}</div></section>`:''}
      ${m.summary?`<section class="detail-section"><h3>KAMPEN</h3><p>${m.summary}</p></section>`:''}
      <section class="detail-section"><h3>KAMPFAKTA</h3><div class="source-note">${m.competition}<br>${m.venue}<br>${m.halfTime?`Pauseresultat: ${m.halfTime}<br>`:''}Sluttresultat: ${m.homeScore}–${m.awayScore}</div></section>
      ${m.nextMatch?`<section class="detail-section"><h3>NESTE KAMP</h3><div class="next-game"><strong>${m.nextMatch.homeAway==='away'?`${m.nextMatch.opponent} – ${m.localTeam==='home'?m.home:m.away}`:`${m.localTeam==='home'?m.home:m.away} – ${m.nextMatch.opponent}`}</strong><br><span class="source-note">${fmtDate(m.nextMatch.date,{weekday:'long',day:'numeric',month:'long'})} ${m.nextMatch.time} · ${m.nextMatch.venue}</span></div></section>`:''}
      <section class="detail-section"><div class="source-note"><strong>Datastatus:</strong> ${m.quality==='demo'?'Denne kampen er demonstrasjonsdata i prototypen.':'Kampresultatet er stadfesta mot offisielle NFF/FIKS-data.'}</div></section>
    </div>`;
  $('#matchDialog').showModal();
}
async function init(){
  const data=await fetch('data/matches.json').then(r=>r.json());
  allMatches=data.matches.filter(m=>Number.isFinite(m.homeScore)&&Number.isFinite(m.awayScore));
  $('#lastUpdated').textContent=new Intl.DateTimeFormat('nn-NO',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(data.generatedAt));
  if(data.photoSubmitUrl&&data.photoSubmitUrl!=='#') $('#photoSubmitLink').href=data.photoSubmitUrl; else $('#photoSubmitLink').addEventListener('click',e=>{e.preventDefault();alert('Her koplar vi inn innsending av kampbilde, til dømes via Tally.');});
  renderHero();renderStats();renderFilters();renderMatches();
  $('#ageFilter').addEventListener('change',renderMatches); $('#clubFilter').addEventListener('change',renderMatches);
  document.querySelectorAll('[data-period]').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('[data-period]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');selectedPeriod=btn.dataset.period;renderMatches()}));
  $('#dialogClose').addEventListener('click',()=>$('#matchDialog').close());
  $('#matchDialog').addEventListener('click',e=>{if(e.target===$('#matchDialog')) $('#matchDialog').close();});
}
init().catch(err=>{console.error(err);$('#matchList').innerHTML='<div class="empty-state">Klarte ikkje å laste kampdata.</div>';});
