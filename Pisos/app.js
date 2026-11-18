/* ═══════════════════════════════════════════════════════════════════
   PISOS — Cercador + Calculadora Libertad Inmobiliaria
   Carlos Galan · Implementacio JS per diordes.github.io/Pisos
   ═══════════════════════════════════════════════════════════════════ */
(function () {
"use strict";

/* ── constants ──────────────────────────────────────────────────── */

const ITP_RATES = {
  'Andalucía':0.07,'Aragón':0.08,'Asturias':0.08,'Baleares':0.08,
  'Canarias':0.065,'Cantabria':0.10,'Castilla y León':0.08,
  'Castilla-La Mancha':0.09,'Cataluña':0.10,'Comunidad de Madrid':0.06,
  'Comunidad Valenciana':0.10,'Extremadura':0.08,'Galicia':0.10,
  'La Rioja':0.07,'Murcia':0.08,'Navarra':0.06,'País Vasco':0.04,
  'Ceuta':0.06,'Melilla':0.06,
};

const QUALITY = {
  A:{label:'A — Mes qualitat',  rentBruta:0.065, rentNeta:0.045, reval:0.03},
  B:{label:'B — Qualitat mitjana',rentBruta:0.08,  rentNeta:0.055, reval:0.03},
  C:{label:'C — Menys qualitat', rentBruta:0.095, rentNeta:0.065, reval:0.03},
};

const TARGETS = {rentBruta:0.07, rentNeta:0.04, rentCP:0.10, tir:0.08, per:15};

/* ── helpers ─────────────────────────────────────────────────────── */

const $  = id => document.getElementById(id);
const num = el => { const v=parseFloat(el?.value); return Number.isFinite(v)?v:null; };
const pct = (v,d=2) => (v*100).toFixed(d)+'%';
const eur = v => v.toLocaleString('ca-ES',{style:'currency',currency:'EUR',maximumFractionDigits:0});
const ok  = (pass) => pass ? '<span class="ok">✓</span>' : '<span class="ko">✗</span>';

/* ── PMT (mortgage payment) ──────────────────────────────────────── */

function pmt(rate,nper,pv){
  if(rate===0) return -pv/nper;
  const x=Math.pow(1+rate,nper);
  return -pv*rate*x/(x-1);
}

/* ── IRR via Newton-Raphson ──────────────────────────────────────── */

function irr(cashflows, guess=0.1, maxIter=200, tol=1e-7){
  let r=guess;
  for(let i=0;i<maxIter;i++){
    let npv=0, dnpv=0;
    for(let t=0;t<cashflows.length;t++){
      const d=Math.pow(1+r,t);
      npv  += cashflows[t]/d;
      dnpv += -t*cashflows[t]/Math.pow(1+r,t+1);
    }
    if(Math.abs(dnpv)<1e-14) break;
    const next=r-npv/dnpv;
    if(Math.abs(next-r)<tol) return next;
    r=next;
  }
  return Number.isFinite(r)&&r>-1?r:null;
}

/* ═══════════════════════════════════════════════════════════════════
   LIBCalculator — Calculadora Libertad Inmobiliaria completa
   ═══════════════════════════════════════════════════════════════════ */

class LIBCalculator {
  constructor(p){
    this.precioCompra      = p.precioCompra      || 0;
    this.rentaMensual      = p.rentaMensual       || 0;
    this.ccaa              = p.ccaa               || 'Cataluña';
    this.reforma           = p.reforma            || 0;
    this.comisionAgencia   = p.comisionAgencia    || 0;
    this.notaria           = p.notaria            ?? 500;
    this.registro          = p.registro           ?? 250;
    this.gestoriaCompra    = p.gestoriaCompra     ?? 300;
    this.pctHipoteca       = p.pctHipoteca        ?? 0.80;
    this.plazoAnos         = p.plazoAnos          ?? 30;
    this.tipoInteres       = p.tipoInteres        ?? 0.035;
    this.comunidadMes      = p.comunidadMes       ?? 35;
    this.ibi               = p.ibi                ?? 180;
    this.seguroHogar       = p.seguroHogar        ?? 100;
    this.seguroVida        = p.seguroVida         ?? 100;
    this.gestoriaHip       = p.gestoriaHip        ?? 300;
    this.tasacion           = p.tasacion           ?? 250;
    this.comisionApertura  = p.comisionApertura   ?? 0;
    this.tramoIRPF         = p.tramoIRPF          ?? 0.30;
    this.pctConstruccion   = p.pctConstruccion    ?? 0.50;
    this.reduccionAlquiler = p.reduccionAlquiler   ?? 0.30;
    this.revalAnual        = p.revalAnual         ?? 0.03;
    this.periodoVenta      = p.periodoVenta       ?? 30;
  }

  /* costos */
  tasaITP()           { return ITP_RATES[this.ccaa]||0.08; }
  importeITP()        { return this.tasaITP()*this.precioCompra; }
  costeVivienda()     { return this.precioCompra+this.importeITP()+this.notaria+this.registro+this.gestoriaCompra+this.reforma+this.comisionAgencia; }
  gastosHipoteca()    { return this.gestoriaHip+this.tasacion+this.comisionApertura; }
  precioEntradaTotal(){ return this.costeVivienda()+this.gastosHipoteca(); }
  importeHipoteca()   { return this.pctHipoteca*this.precioCompra; }
  capitalPropio()     { return this.precioEntradaTotal()-this.importeHipoteca(); }

  /* hipoteca */
  cuotaMensual(){ return -pmt(this.tipoInteres/12, this.plazoAnos*12, this.importeHipoteca()); }
  cuotaAnual()  { return this.cuotaMensual()*12; }
  interesesPrimerAno(){
    const r=this.tipoInteres/12;
    let cap=this.importeHipoteca(), intAcum=0;
    for(let m=0;m<12;m++){ const i=cap*r; intAcum+=i; cap-=(this.cuotaMensual()-i); }
    return intAcum;
  }
  interesesAnualesMedios(){ return (this.cuotaAnual()*this.plazoAnos-this.importeHipoteca())/this.plazoAnos; }
  parteDevolucionAnual(){ return this.cuotaAnual()-this.interesesAnualesMedios(); }

  /* ingressos i despeses */
  rentaAnual(){ return this.rentaMensual*12; }

  gastosAnuales(){
    const ra=this.rentaAnual();
    const comunidad=this.comunidadMes*12;
    const mantenimiento=0.10*ra;
    const segImpago=0.05*ra;
    const vacantes=0.05*ra;
    const intHip=this.interesesAnualesMedios();
    return {
      comunidad, mantenimiento,
      seguroHogar:this.seguroHogar, seguroVida:this.seguroVida,
      segImpago, ibi:this.ibi, intHip, vacantes,
      total: comunidad+mantenimiento+this.seguroHogar+this.seguroVida+segImpago+this.ibi+intHip+vacantes,
    };
  }

  amortizacionFiscal(){
    return 0.03*(this.pctConstruccion*(this.precioCompra+this.importeITP()+this.notaria+this.registro+this.gestoriaCompra)+this.reforma);
  }

  beneficioAntesImpuestos(){ return this.rentaAnual()-this.gastosAnuales().total; }

  impuestos(){
    const base=this.beneficioAntesImpuestos()-this.amortizacionFiscal();
    if(base<=0) return 0;
    return base*(1-this.reduccionAlquiler)*this.tramoIRPF;
  }

  beneficioDespuesImpuestos(){ return this.beneficioAntesImpuestos()-this.impuestos(); }

  /* metriques */
  rentabilidadBruta(){ const pet=this.precioEntradaTotal(); return pet?this.rentaAnual()/pet:0; }

  rentabilidadNeta(){
    const pet=this.precioEntradaTotal();
    if(!pet) return 0;
    return (this.beneficioDespuesImpuestos()+this.impuestos()+this.interesesAnualesMedios())/pet;
  }

  cashflowAnual(){ return this.beneficioDespuesImpuestos()-this.parteDevolucionAnual(); }
  cashflowMensual(){ return this.cashflowAnual()/12; }

  roce(){ const cp=this.capitalPropio(); return cp?this.cashflowAnual()/cp:0; }
  patrimonioNetoCreado(){ const cp=this.capitalPropio(); return cp?this.parteDevolucionAnual()/cp:0; }
  revalorizacionVsCapital(){ const cp=this.capitalPropio(); return cp?this.revalAnual*this.precioCompra/cp:0; }
  rentCapitalPropio(){ return this.roce()+this.patrimonioNetoCreado()+this.revalorizacionVsCapital(); }

  per(){ const ra=this.rentaAnual(); return ra?this.precioEntradaTotal()/ra:999; }

  /* TIR */
  calcularTIR(){
    const N=this.periodoVenta;
    const cp=this.capitalPropio();
    if(cp<=0) return null;
    const ra=this.rentaAnual();
    const ga=this.gastosAnuales().total;
    const imp=this.impuestos();
    const cuota=this.cuotaAnual();
    const reval=this.revalAnual;

    // cash flows
    const cf=[- cp];
    for(let y=1;y<=N;y++){
      const factor=Math.pow(1+reval,y-1);
      const income=ra*factor;
      const expense=(ga-this.interesesAnualesMedios())*factor + this.interesesAnualesMedios();
      const tax=Math.max(0,(income-expense-this.amortizacionFiscal())*(1-this.reduccionAlquiler)*this.tramoIRPF);
      const net=income-expense-tax-cuota;
      cf.push(net);
    }

    // venda any N
    const valorVenda=this.precioCompra*Math.pow(1+reval,N-1);
    const amortAcum=this.amortizacionFiscal()*N;
    const ganancia=valorVenda-(this.costeVivienda()-amortAcum);
    // IRPF ganancia patrimonial progressiu
    let irpfGP=0;
    const brackets=[[6000,0.19],[44000,0.21],[150000,0.23],[100000,0.27],[Infinity,0.28]];
    let rem=Math.max(0,ganancia);
    for(const [size,rate] of brackets){
      const chunk=Math.min(rem,size); irpfGP+=chunk*rate; rem-=chunk; if(rem<=0) break;
    }
    // plusvalia municipal aprox
    const plusvalia=Math.max(0,0.30*0.03*ganancia);
    // hipoteca pendent (aproximat)
    let hipPend=this.importeHipoteca();
    const rM=this.tipoInteres/12; const cuotaM=this.cuotaMensual();
    for(let m=0;m<N*12&&m<this.plazoAnos*12;m++){
      hipPend-=(cuotaM-hipPend*rM);
    }
    hipPend=Math.max(0,hipPend);

    const proceedsVenda=valorVenda-irpfGP-plusvalia-hipPend;
    cf[N]+=proceedsVenda;

    return irr(cf,0.08);
  }

  precioMaximoOferta(calidad='B'){
    const q=QUALITY[calidad];
    if(!q||!this.rentaAnual()) return {viaBruta:0,viaNeta:0};
    const viaBruta=this.rentaAnual()/q.rentBruta - this.comisionAgencia - this.reforma - this.importeITP() - this.notaria - this.registro - this.gestoriaCompra - this.gastosHipoteca();
    return {viaBruta:Math.max(0,viaBruta)};
  }

  puntuacion(){
    let s=0;
    const tir=this.calcularTIR();
    if(this.rentabilidadBruta()>=TARGETS.rentBruta) s++;
    if(this.rentabilidadNeta()>=TARGETS.rentNeta)   s++;
    if(this.rentCapitalPropio()>=TARGETS.rentCP)     s++;
    if(tir!==null&&tir>=TARGETS.tir)                 s++;
    if(this.per()<TARGETS.per)                       s++;
    if(this.cashflowAnual()>0)                       s++;
    // calitat-based
    const q=QUALITY['B'];
    if(this.rentabilidadBruta()>=q.rentBruta)        s++;
    if(this.rentabilidadNeta()>=q.rentNeta)           s++;
    return s;
  }
}

/* make available globally for console testing */
window.LIBCalculator = LIBCalculator;

/* ═══════════════════════════════════════════════════════════════════
   UI — Portal URL builders
   ═══════════════════════════════════════════════════════════════════ */

function getFilters(){
  return {
    op:    $('fOp')?.value||'buy',
    pMin:  num($('fPriceMin')),
    pMax:  num($('fPriceMax')),
    sMin:  num($('fSizeMin')),
    sMax:  num($('fSizeMax')),
    rooms: $('fRooms')?.value||'any',
    baths: $('fBaths')?.value||'any',
  };
}

function getCity(){
  const id=$('fCity')?.value;
  return window.PISOS_CITIES.find(c=>c.id===id);
}

function idealistaURL(city,f){
  const op=f.op==='rent'?'alquiler-viviendas':'venta-viviendas';
  const p=[];
  if(f.pMin!=null) p.push('precio-desde_'+Math.round(f.pMin));
  if(f.pMax!=null) p.push('precio-hasta_'+Math.round(f.pMax));
  if(f.sMin!=null) p.push('metros-cuadrados-mas-de_'+Math.round(f.sMin));
  if(f.sMax!=null) p.push('metros-cuadrados-menos-de_'+Math.round(f.sMax));
  const filt=p.length?'con-'+p.join(',')+'/':'';
  return `https://www.idealista.com/${op}/${city.idealista}/${filt}`;
}

function fotocasaURL(city,f){
  const op=f.op==='rent'?'alquiler':'comprar';
  const q=new URLSearchParams();
  if(f.pMin!=null) q.set('minPrice',String(Math.round(f.pMin)));
  if(f.pMax!=null) q.set('maxPrice',String(Math.round(f.pMax)));
  if(f.sMin!=null) q.set('minSurface',String(Math.round(f.sMin)));
  if(f.sMax!=null) q.set('maxSurface',String(Math.round(f.sMax)));
  if(f.rooms!=='any') q.set('minRooms',f.rooms);
  if(f.baths!=='any') q.set('minBathrooms',f.baths);
  const qs=q.toString();
  return `https://www.fotocasa.es/es/${op}/viviendas/${city.fotocasa}/l${qs?'?'+qs:''}`;
}

function habitacliaURL(city,f){
  const op=f.op==='rent'?'alquiler':'viviendas';
  const q=new URLSearchParams();
  if(f.pMax!=null) q.set('pmax',String(Math.round(f.pMax)));
  if(f.sMin!=null) q.set('sm',String(Math.round(f.sMin)));
  const qs=q.toString();
  return `https://www.habitaclia.com/${op}-${city.habitaclia}.htm${qs?'?'+qs:''}`;
}

function milanunciosURL(city,f){
  const op=f.op==='rent'?'alquiler':'venta';
  const q=new URLSearchParams();
  q.set('s',city.milanuncios);
  if(f.pMin!=null) q.set('desde',String(Math.round(f.pMin)));
  if(f.pMax!=null) q.set('hasta',String(Math.round(f.pMax)));
  return `https://www.milanuncios.com/viviendas-en-${op}/?${q.toString()}`;
}

function bankSearchURL(portal,city){
  return `https://www.google.com/search?q=site:${portal}+venta+viviendas+${encodeURIComponent(city.label)}`;
}

/* ═══════════════════════════════════════════════════════════════════
   UI — Render functions
   ═══════════════════════════════════════════════════════════════════ */

function renderCities(){
  const sel=$('fCity');
  if(!sel) return;
  sel.innerHTML=window.PISOS_CITIES.map(c=>`<option value="${c.id}">${c.label}</option>`).join('');
  // Also populate ccaa dropdown for calculator
  const ccaaSel=$('cCCAA');
  if(ccaaSel){
    const ccaas=[...new Set(Object.keys(ITP_RATES))].sort();
    ccaaSel.innerHTML=ccaas.map(c=>`<option value="${c}"${c==='Cataluña'?' selected':''}>${c} (${(ITP_RATES[c]*100).toFixed(1)}%)</option>`).join('');
  }
}

function renderPortals(){
  const city=getCity(); const f=getFilters();
  const el=$('portals');
  if(!el||!city) return;

  const portals=[
    {name:'Idealista',   icon:'🏠', url:idealistaURL(city,f)},
    {name:'Fotocasa',    icon:'📸', url:fotocasaURL(city,f)},
    {name:'Habitaclia',  icon:'🏡', url:habitacliaURL(city,f)},
    {name:'Milanuncios', icon:'📋', url:milanunciosURL(city,f)},
  ];

  const banks=[
    {name:'Haya Inmobiliaria',    domain:'hayainmobiliaria.com'},
    {name:'Servihabitat',         domain:'servihabitat.com'},
    {name:'Solvia (Sabadell)',    domain:'solvia.es'},
    {name:'Altamira',             domain:'altamirainmuebles.com'},
    {name:'Aliseda',              domain:'alisedainmobiliaria.com'},
    {name:'CaixaBank Inmuebles',  domain:'inmuebles.caixabank.es'},
    {name:'Anticipa',             domain:'anticipa.com'},
  ];

  let html='<div class="portal-grid">';
  portals.forEach(p=>{
    html+=`<a class="portal-btn" href="${p.url}" target="_blank" rel="noopener">${p.icon} ${p.name}</a>`;
  });
  html+='</div>';

  html+=`<h3 class="sub-h">🏦 Pisos de bancs <small>(Curs LIB, modul 3.16)</small></h3>
    <p class="note">Els bancs sovint venen mes barat perque volen desfer-se dels actius rapids.</p>
    <div class="portal-grid bank">`;
  banks.forEach(b=>{
    html+=`<a class="portal-btn bank" href="${bankSearchURL(b.domain,city)}" target="_blank" rel="noopener">🏦 ${b.name}</a>`;
  });
  html+='</div>';

  el.innerHTML=html;
}

function renderZones(){
  const city=getCity();
  const el=$('zones');
  if(!el) return;
  const z=window.PISOS_ZONES?.[city?.id];
  if(!z){
    el.innerHTML='<p class="empty">Sense notes de zones per aquesta ciutat.</p>';
    return;
  }
  let html=`<div class="zone-grid">
    <div class="zone-card good"><h3>🟢 Zones bones</h3><ul>${z.bones.map(x=>'<li>'+x+'</li>').join('')}</ul></div>
    <div class="zone-card bad"><h3>🔴 Mes cautela</h3><ul>${z.cautela.map(x=>'<li>'+x+'</li>').join('')}</ul></div>
  </div>`;
  if(z.font) html+=`<p class="zone-source">Font: ${z.font}</p>`;
  el.innerHTML=html;
}

function renderTelegram(){
  const city=getCity();
  const el=$('telegram');
  if(!el) return;
  const tg=window.PISOS_TELEGRAM;
  const items=(tg.channels||[]).filter(c=>c.city==='general'||c.city===city?.id);
  const tipsHtml=(tg.tips||[]).map(t=>'<li>'+t+'</li>').join('');
  const chHtml=items.map(c=>{
    const href=`https://www.google.com/search?q=${encodeURIComponent(c.query)}`;
    return `<a class="tg-btn" href="${href}" target="_blank" rel="noopener">💬 ${c.label}${c.note?' <small>('+c.note+')</small>':''}</a>`;
  }).join('');
  el.innerHTML=`<div class="tg-tips"><ul>${tipsHtml}</ul></div><div class="tg-grid">${chHtml}</div>`;
}

function openAll(){
  const city=getCity(); if(!city) return;
  const f=getFilters();
  [idealistaURL,fotocasaURL,habitacliaURL,milanunciosURL].forEach((fn,i)=>{
    setTimeout(()=>window.open(fn(city,f),'_blank','noopener'),i*400);
  });
}

/* ═══════════════════════════════════════════════════════════════════
   UI — Calculator section
   ═══════════════════════════════════════════════════════════════════ */

function runCalculator(){
  const el=$('calcResult');
  if(!el) return;

  const p={
    precioCompra:    num($('cPrecio'))||0,
    rentaMensual:    num($('cRenta'))||0,
    ccaa:            $('cCCAA')?.value||'Cataluña',
    reforma:         num($('cReforma'))||0,
    comisionAgencia: num($('cComision'))||0,
    pctHipoteca:     (num($('cPctHip'))||80)/100,
    tipoInteres:     (num($('cInteres'))||3.5)/100,
    plazoAnos:       num($('cPlazo'))||30,
    comunidadMes:    num($('cComunidad'))||35,
    ibi:             num($('cIBI'))||180,
  };

  if(!p.precioCompra||!p.rentaMensual){
    el.innerHTML='<p class="empty">Introdueix preu i lloguer estimat.</p>';
    return;
  }

  const c=new LIBCalculator(p);
  const tir=c.calcularTIR();
  const tirVal=tir!==null?tir:0;
  const score=c.puntuacion();
  const oferta=c.precioMaximoOferta('B');

  const scoreClass=score>=6?'score-good':score>=4?'score-mid':'score-bad';

  el.innerHTML=`
    <div class="calc-score ${scoreClass}">${score}/8</div>
    <div class="calc-metrics">
      <div class="metric">${ok(c.rentabilidadBruta()>=TARGETS.rentBruta)} Rent. Bruta <strong>${pct(c.rentabilidadBruta())}</strong> <small>(obj &gt;7%)</small></div>
      <div class="metric">${ok(c.rentabilidadNeta()>=TARGETS.rentNeta)} Rent. Neta <strong>${pct(c.rentabilidadNeta())}</strong> <small>(obj &gt;4%)</small></div>
      <div class="metric">${ok(c.rentCapitalPropio()>=TARGETS.rentCP)} Rent. Cap. Propi <strong>${pct(c.rentCapitalPropio())}</strong> <small>(obj &gt;10%)</small></div>
      <div class="metric">${ok(tirVal>=TARGETS.tir)} TIR <strong>${tir!==null?pct(tir):'N/A'}</strong> <small>(obj &gt;8%)</small></div>
      <div class="metric">${ok(c.per()<TARGETS.per)} PER <strong>${c.per().toFixed(1)} anys</strong> <small>(obj &lt;15)</small></div>
      <div class="metric">${ok(c.cashflowMensual()>0)} Cashflow <strong>${eur(Math.round(c.cashflowMensual()))}/mes</strong></div>
    </div>
    <div class="calc-detail">
      <table>
        <tr><td>Preu entrada total</td><td>${eur(c.precioEntradaTotal())}</td></tr>
        <tr><td>Hipoteca (${Math.round(c.pctHipoteca*100)}%)</td><td>${eur(c.importeHipoteca())}</td></tr>
        <tr><td>Capital propi</td><td>${eur(c.capitalPropio())}</td></tr>
        <tr><td>Quota hipoteca/mes</td><td>${eur(Math.round(c.cuotaMensual()))}</td></tr>
        <tr><td>ITP (${pct(c.tasaITP(),1)})</td><td>${eur(c.importeITP())}</td></tr>
        <tr><td>Despeses anuals</td><td>${eur(Math.round(c.gastosAnuales().total))}</td></tr>
        <tr><td>ROCE</td><td>${pct(c.roce())}</td></tr>
        <tr><td>Patrimoni net creat</td><td>${pct(c.patrimonioNetoCreado())}</td></tr>
        <tr><td>Revaloritzacio vs capital</td><td>${pct(c.revalorizacionVsCapital())}</td></tr>
      </table>
      <div class="calc-offer">
        <strong>Preu max. oferta (qualitat B):</strong> ${eur(Math.round(oferta.viaBruta))} <small>via Rent. Bruta</small>
      </div>
    </div>
  `;
}

/* ═══════════════════════════════════════════════════════════════════
   UI — Import JSON results from Colab
   ═══════════════════════════════════════════════════════════════════ */

let importedResults=[];

function handleFileImport(e){
  const file=e.target.files[0];
  if(!file) return;
  const reader=new FileReader();
  reader.onload=function(ev){
    try{
      const data=JSON.parse(ev.target.result);
      importedResults=Array.isArray(data)?data:data.resultats||data.results||[];
      renderResults();
    }catch(err){
      alert('Error llegint JSON: '+err.message);
    }
  };
  reader.readAsText(file);
}

function renderResults(){
  const el=$('results');
  if(!el) return;

  if(!importedResults.length){
    el.innerHTML=`<p class="empty">Cap resultat importat. Executa l'script de Colab i importa el JSON aqui.</p>`;
    return;
  }

  // compute metrics for each
  const rows=importedResults.map(r=>{
    const c=new LIBCalculator({
      precioCompra: r.precio||r.precio_compra||0,
      rentaMensual: r.renta||r.renta_mensual||0,
      ccaa: r.ccaa||r.comunidad_autonoma||'Cataluña',
      reforma: r.reforma||0,
      pctHipoteca: r.pct_hipoteca||0.80,
      tipoInteres: r.tipo_interes||0.035,
      comunidadMes: r.comunidad_mensual||35,
      ibi: r.ibi||180,
    });
    const tir=c.calcularTIR();
    return {
      ...r,
      rentBruta: c.rentabilidadBruta(),
      rentNeta: c.rentabilidadNeta(),
      rentCP: c.rentCapitalPropio(),
      tir: tir,
      per: c.per(),
      cashflow: c.cashflowMensual(),
      score: c.puntuacion(),
    };
  }).sort((a,b)=>b.score-a.score || b.rentBruta-a.rentBruta);

  let html=`<p>${rows.length} pisos analitzats</p>`;
  html+='<div class="table-wrap"><table class="results-table"><thead><tr>';
  html+='<th>Pts</th><th>Pis</th><th>Preu</th><th>m²</th><th>Llog</th><th>R.Brut</th><th>R.Net</th><th>R.CP</th><th>TIR</th><th>PER</th><th>CF/m</th><th>Link</th>';
  html+='</tr></thead><tbody>';

  rows.forEach(r=>{
    const cls=r.score>=6?'row-good':r.score>=4?'row-mid':'row-bad';
    const nombre=r.direccion||r.nombre||r.address||'—';
    const url=r.url||r.link||'';
    html+=`<tr class="${cls}">
      <td><strong>${r.score}</strong>/8</td>
      <td title="${nombre}">${nombre.substring(0,30)}</td>
      <td>${eur(r.precio||r.precio_compra||0)}</td>
      <td>${r.m2||r.superficie_m2||'—'}</td>
      <td>${eur(r.renta||r.renta_mensual||0)}</td>
      <td>${pct(r.rentBruta)}</td>
      <td>${pct(r.rentNeta)}</td>
      <td>${pct(r.rentCP)}</td>
      <td>${r.tir!==null?pct(r.tir):'—'}</td>
      <td>${r.per.toFixed(1)}</td>
      <td>${eur(Math.round(r.cashflow))}</td>
      <td>${url?`<a href="${url}" target="_blank">🔗</a>`:''}</td>
    </tr>`;
  });

  html+='</tbody></table></div>';
  el.innerHTML=html;
}

/* ═══════════════════════════════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════════════════════════════ */

function refresh(){
  renderPortals();
  renderZones();
  renderTelegram();
}

document.addEventListener('DOMContentLoaded',()=>{
  renderCities();
  refresh();
  renderResults();

  // filters
  ['fCity','fOp','fPriceMin','fPriceMax','fSizeMin','fSizeMax','fRooms','fBaths'].forEach(id=>{
    $(id)?.addEventListener('input',refresh);
  });

  // open all
  $('btnOpenAll')?.addEventListener('click',openAll);

  // calculator — live update
  ['cPrecio','cRenta','cCCAA','cReforma','cComision','cPctHip','cInteres','cPlazo','cComunidad','cIBI'].forEach(id=>{
    $(id)?.addEventListener('input',runCalculator);
  });

  // file import
  $('fileImport')?.addEventListener('change',handleFileImport);
});

})();
