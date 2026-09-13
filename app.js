const TARGET_CLUBS = [
  'Vestnes Varfjell','Tomrefjord','Fiksdal/Rekdal','Ørskog','Stordal','Skodje',
  'Brattvåg','Ravn','Norborg','HaNo','Harøy','Lepsøy','Hildre'
];

let allMatches = [];
let selectedPeriod = 'all';
const $ = (selector) => document.querySelector(selector);
const esc = (value='') => String(value).replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
const fmtDate = (iso, opts={}) => new Intl.DateTimeFormat('nn-NO', opts).format(new Date(`${iso}T12:00:00`));

function initials(team){
  return String(team).split(/[\s/]+/).filter(Boolean).slice(0,3).map(x=>x[0]).join('').toUpperCase();
}

function isLocalName(name){
  const lower = String(name).toLowerCase();
  return TARGET_CLUBS.some(club => lower.includes(club.toLowerCase()));
}

function ageLabel(age){
  if(age === 'MENN') return 'Menn senior';
  if(age === 'KVINNER') return 'Kvinner senior';
  if(age === 'SENIOR') return 'Senior';
  return age;
}

function localOutcome(match){
  if(match.localTeam === 'both') return {key:'derby', label:'LOKALDERBY'};
  const localScore = match.localTeam === 'home' ? match.homeScore : match.awayScore;
  const otherScore = match.localTeam === 'home' ? match.awayScore : match.homeScore;
  if(localScore > otherScore) return {key:'win', label:'SIGER'};
  if(localScore < otherScore) return {key:'loss', label:'TAP'};
  return {key:'draw', label:'UAVGJORT'};
}

function periodMatch(match){
  if(selectedPeriod === 'all') return true;
  const today = new Date();
  today.setHours(12,0,0,0);
  const date = new Date(`${match.date}T12:00:00`);
  const diff = Math.floor((today - date) / 86400000);
  if(selectedPeriod === 'week') return diff >= 0 && diff < 7;
  if(selectedPeriod === 'month') return diff >= 0 && diff < 30;
  return true;
}

function filtered(){
  const age = $('#ageFilter').value;
  const club = $('#clubFilter').value;
  return allMatches
    .filter(periodMatch)
    .filter(match => age === 'all' || match.age === age)
    .filter(match => club === 'all' || match.home.toLowerCase().includes(club.toLowerCase()) || match.away.toLowerCase().includes(club.toLowerCase()));
}

function renderHero(){
  const match = allMatches[0];
  if(!match){
    $('#heroScore').innerHTML = '<div class="featured-card featured-empty">Ingen ferdigspelte kampar registrert enno.</div>';
    return;
  }
  const outcome = localOutcome(match);
  const scorers = (match.events || []).filter(event => event.type === 'goal' && (match.localTeam === 'both' || event.team === match.localTeam));

  $('#heroScore').innerHTML = `
    <article class="featured-card">
      <div class="featured-glow"></div>
      <div class="featured-top">
        <div><span class="featured-kicker">SIST REGISTRERT</span><strong>${esc(ageLabel(match.age))} · ${esc(match.competition)}</strong></div>
        <span class="verified-badge">✓ NFF</span>
      </div>
      <div class="featured-teams">
        <div class="featured-team ${isLocalName(match.home)?'local':''}">
          <div class="crest">${esc(initials(match.home))}</div>
          <span>${esc(match.home)}</span>
        </div>
        <div class="featured-result-wrap">
          <div class="featured-status">SLUTT</div>
          <div class="featured-score">${match.homeScore}<i>–</i>${match.awayScore}</div>
          <div class="outcome outcome-${outcome.key}">${outcome.label}</div>
        </div>
        <div class="featured-team ${isLocalName(match.away)?'local':''}">
          <div class="crest">${esc(initials(match.away))}</div>
          <span>${esc(match.away)}</span>
        </div>
      </div>
      <div class="featured-meta">
        <span>${fmtDate(match.date,{weekday:'long',day:'numeric',month:'long'})}</span>
        <span>•</span><span>${esc(match.time || '')}</span>
        ${match.venue?`<span>•</span><span>${esc(match.venue)}</span>`:''}
      </div>
      ${scorers.length ? `<div class="featured-scorers">${scorers.map(event=>`<span class="scorer-pill">⚽ ${esc(event.player)}${event.minute!=null?` ${event.minute}'`:''}</span>`).join('')}</div>` : ''}
      <button class="featured-open" data-hero-id="${esc(match.id)}">Sjå kampfakta <span>→</span></button>
    </article>`;

  $('[data-hero-id]').addEventListener('click', () => openMatch(match.id));
}

function renderStats(){
  const goals = allMatches.reduce((sum, match) => sum + match.homeScore + match.awayScore, 0);
  const localWins = allMatches.filter(match => localOutcome(match).key === 'win').length;
  const localTeams = new Set(allMatches.flatMap(match => [match.home,match.away].filter(isLocalName)));
  $('#statsStrip').innerHTML = `
    <div class="stat"><strong>${allMatches.length}</strong><span>verifiserte resultat</span></div>
    <div class="stat"><strong>${goals}</strong><span>mål i desse kampane</span></div>
    <div class="stat"><strong>${localWins}</strong><span>lokale sigrar</span></div>
    <div class="stat"><strong>${localTeams.size}</strong><span>lokale lag registrert</span></div>`;
}

function renderFilters(){
  const ages = [...new Set(allMatches.map(match=>match.age))].sort((a,b)=>{
    const rank = value => value === 'MENN' ? 100 : value === 'KVINNER' ? 101 : Number(value.replace(/\D/g,'')) || 99;
    return rank(a)-rank(b) || a.localeCompare(b,'nn');
  });
  ages.forEach(age => $('#ageFilter').insertAdjacentHTML('beforeend', `<option value="${esc(age)}">${esc(ageLabel(age))}</option>`));
  TARGET_CLUBS.forEach(club => $('#clubFilter').insertAdjacentHTML('beforeend', `<option value="${esc(club)}">${esc(club)}</option>`));
}

function matchCard(match){
  const outcome = localOutcome(match);
  return `<article class="match-card outcome-card-${outcome.key}" tabindex="0" data-id="${esc(match.id)}" role="button" aria-label="Opne ${esc(match.home)} mot ${esc(match.away)}">
    <div class="match-meta">
      <div class="match-class"><span>${esc(ageLabel(match.age))}</span>${esc(match.competition)}</div>
      <div class="match-place">${esc(match.venue || 'Bane ikkje oppgitt')} · ${esc(match.time || '')}</div>
    </div>
    <div class="match-teams">
      <div class="team-line ${isLocalName(match.home)?'local':''}">
        <div class="mini-crest">${esc(initials(match.home))}</div>
        <div class="team-name">${esc(match.home)}</div>
        <div class="team-score">${match.homeScore}</div>
      </div>
      <div class="team-line ${isLocalName(match.away)?'local':''}">
        <div class="mini-crest">${esc(initials(match.away))}</div>
        <div class="team-name">${esc(match.away)}</div>
        <div class="team-score">${match.awayScore}</div>
      </div>
    </div>
    <div class="match-side">
      <div class="outcome outcome-${outcome.key}">${outcome.label}</div>
      <div class="verified-mini">✓ NFF</div>
      <div class="arrow">→</div>
    </div>
  </article>`;
}

function renderMatches(){
  const list = filtered().sort((a,b)=>`${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`));
  $('#resultCount').textContent = `${list.length} ${list.length === 1 ? 'kamp' : 'kampar'}`;
  $('#emptyState').hidden = list.length > 0;
  let html = '';
  let lastDate = '';

  list.forEach(match => {
    if(match.date !== lastDate){
      lastDate = match.date;
      html += `<div class="date-heading"><span>${fmtDate(match.date,{weekday:'long',day:'numeric',month:'long',year:'numeric'})}</span></div>`;
    }
    html += matchCard(match);
  });

  $('#matchList').innerHTML = html;
  document.querySelectorAll('.match-card').forEach(card => {
    card.addEventListener('click',()=>openMatch(card.dataset.id));
    card.addEventListener('keydown',event=>{
      if(event.key === 'Enter' || event.key === ' '){
        event.preventDefault();
        openMatch(card.dataset.id);
      }
    });
  });
}

function openMatch(id){
  const match = allMatches.find(item => item.id === id);
  if(!match) return;
  const outcome = localOutcome(match);
  const localEvents = (match.events || []).filter(event => match.localTeam === 'both' || event.team === match.localTeam);
  const sourceLink = match.sourceUrl ? `<a class="source-link" href="${esc(match.sourceUrl)}" target="_blank" rel="noopener">Opne NFF-kjelda <span>↗</span></a>` : '';

  $('#dialogContent').innerHTML = `
    <div class="dialog-hero">
      <div class="dialog-label"><span>${esc(ageLabel(match.age))}</span> ${esc(match.competition)}</div>
      <div class="dialog-scoreboard">
        <div class="dialog-team ${isLocalName(match.home)?'local':''}"><div class="dialog-crest">${esc(initials(match.home))}</div><strong>${esc(match.home)}</strong></div>
        <div class="dialog-result-block"><span>SLUTT</span><div class="dialog-result">${match.homeScore}<i>–</i>${match.awayScore}</div><div class="outcome outcome-${outcome.key}">${outcome.label}</div></div>
        <div class="dialog-team ${isLocalName(match.away)?'local':''}"><div class="dialog-crest">${esc(initials(match.away))}</div><strong>${esc(match.away)}</strong></div>
      </div>
      <div class="dialog-facts">
        <span>${fmtDate(match.date,{weekday:'long',day:'numeric',month:'long',year:'numeric'})}</span>
        ${match.time?`<span>•</span><span>${esc(match.time)}</span>`:''}
        ${match.venue?`<span>•</span><span>${esc(match.venue)}</span>`:''}
      </div>
    </div>
    <div class="dialog-body">
      ${localEvents.length ? `<section class="detail-section"><div class="detail-heading"><h3>LOKALE MÅL</h3><span>${localEvents.length}</span></div><div class="timeline">${localEvents.map(event=>`<div class="event"><div class="event-time">${event.minute!=null?`${event.minute}'`:'–'}</div><div class="event-ball">⚽</div><div class="event-text">${esc(event.player)}</div></div>`).join('')}</div></section>` : `
        <section class="detail-section compact"><div class="detail-heading"><h3>KAMPDETALJAR</h3></div><p class="muted-copy">Vi har førebels berre stadfesta sluttresultatet og dei grunnleggjande kampfakta for denne kampen.</p></section>`}
      ${match.summary?`<section class="detail-section"><div class="detail-heading"><h3>KAMPEN</h3></div><p>${esc(match.summary)}</p></section>`:''}
      <section class="detail-section">
        <div class="detail-heading"><h3>KAMPFAKTA</h3><span class="verified-badge">✓ NFF</span></div>
        <dl class="facts-grid">
          <div><dt>Turnering</dt><dd>${esc(match.competition)}</dd></div>
          <div><dt>Bane</dt><dd>${esc(match.venue || 'Ikkje oppgitt')}</dd></div>
          <div><dt>Sluttresultat</dt><dd>${match.homeScore}–${match.awayScore}</dd></div>
          <div><dt>NFF-kampnr.</dt><dd>${esc(match.matchNumber || '–')}</dd></div>
          ${match.halfTime?`<div><dt>Pause</dt><dd>${esc(match.halfTime)}</dd></div>`:''}
        </dl>
      </section>
      ${match.nextMatch?`<section class="detail-section"><div class="detail-heading"><h3>NESTE KAMP</h3></div><div class="next-game"><strong>${esc(match.nextMatch.opponent)}</strong><span>${fmtDate(match.nextMatch.date,{weekday:'long',day:'numeric',month:'long'})} ${esc(match.nextMatch.time || '')}${match.nextMatch.venue?` · ${esc(match.nextMatch.venue)}`:''}</span></div></section>`:''}
      <section class="detail-section source-section">
        <div><strong>Kjelde: Norges Fotballforbund</strong><p>Resultatet er kontrollert mot offisielle kampdata på fotball.no.</p></div>
        ${sourceLink}
      </section>
    </div>`;
  $('#matchDialog').showModal();
}

async function init(){
  const response = await fetch('data/matches.json', {cache:'no-store'});
  if(!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  allMatches = data.matches
    .filter(match => Number.isFinite(match.homeScore) && Number.isFinite(match.awayScore))
    .sort((a,b)=>`${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`));

  $('#lastUpdated').textContent = new Intl.DateTimeFormat('nn-NO',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(data.generatedAt));
  if(data.photoSubmitUrl && data.photoSubmitUrl !== '#'){
    $('#photoSubmitLink').href = data.photoSubmitUrl;
    $('#photoSubmitLink').target = '_blank';
    $('#photoSubmitLink').rel = 'noopener';
  } else {
    $('#photoSubmitLink').addEventListener('click',event=>{
      event.preventDefault();
      alert('Her koplar vi inn skjemaet for innsending av kampbilde.');
    });
  }

  renderHero();
  renderStats();
  renderFilters();
  renderMatches();

  $('#ageFilter').addEventListener('change',renderMatches);
  $('#clubFilter').addEventListener('change',renderMatches);
  document.querySelectorAll('[data-period]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-period]').forEach(item=>item.classList.remove('active'));
    button.classList.add('active');
    selectedPeriod = button.dataset.period;
    renderMatches();
  }));
  $('#dialogClose').addEventListener('click',()=>$('#matchDialog').close());
  $('#matchDialog').addEventListener('click',event=>{
    if(event.target === $('#matchDialog')) $('#matchDialog').close();
  });
}

init().catch(error=>{
  console.error(error);
  $('#matchList').innerHTML = '<div class="empty-state"><strong>Klarte ikkje å laste kampdata.</strong><span>Prøv igjen om litt.</span></div>';
});
