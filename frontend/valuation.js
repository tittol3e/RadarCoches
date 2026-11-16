'use strict';

async function tasador(){
 const [rawComparables,rawListings]=await Promise.all([api('/api/comparables'),api('/api/listings')]);
 const comps=arr(rawComparables),listings=arr(rawListings);
 const savedId=sessionStorage.getItem('radar_vehicle_id')||'';
 const root=el('div',{},[head('Tasador de vehículos','Una estimación trazable empieza con comparables suficientes.'),notice('Los comparables son precios solicitados. El descuento de reventa y la oferta inicial son hipótesis que tú defines; no representan ventas verificadas.','info')]);
 const formPanel=panel('Vehículo a valorar');
 const vf=form([
  field('selected_listing','Vehículo guardado en el Radar (opcional)','select',savedId,{wide:true,items:[['','Introducir un vehículo sin asociar'],...listings.map(x=>[x.id,[x.brand,x.model,x.year].filter(Boolean).join(' ')])]}),
  field('brand','Marca','text','',{required:true,list:'catalog-brands'}),field('model','Modelo','text','',{required:true,list:'catalog-models'}),field('generation','Generación','text','',{list:'catalog-generations'}),field('version','Versión','text','',{list:'catalog-versions'}),field('engine','Motorización','text','',{list:'catalog-engines'}),field('year','Año','number','',{required:true,step:1}),field('km','Kilómetros','number','',{required:true,step:1}),field('km_slider','Ajustar kilómetros','range','100000'),field('power','Potencia del motor (CV)','number'),field('fuel','Combustible'),field('transmission','Cambio'),field('province','Ubicación'),...vehicleExtras(),field('purchase','Compra prevista (€)','number',''),field('target_profit','Beneficio objetivo (€)','number',0),field('discount_pct','Descuento hipotético sobre anunciado (%)','number',0,{hint:'Debe justificarse con evidencia. Cero no implica venta asegurada.'}),field('opening_discount_pct','Descuento inicial negociador (%)','number',0),field('tax_rate','Impuesto proporcional manual (%)','number',0),field('tax_base_floor','Base fiscal mínima comprobada (€)','number',0)
 ],'Calcular con los comparables seleccionados',async d=>calculateValuation(d,true));
 const result=el('div');
 const selected=el('div',{},[txt('h3','Comparables que se utilizarán')]);
 if(!comps.length)selected.append(notice('No existe una tasación fiable con los datos disponibles. Añade comparables observados y verificados.'));
 for(const c of comps)selected.append(el('label',{class:'check-label'},[el('input',{type:'checkbox',name:'comparable_id',value:c.id,checked:c.verified}),[c.brand,c.model,c.year,num(c.km)+' km',euro(c.price),c.verified?'comprobado':'sin verificar'].join(' · ')]));
 const costBox=costEditor();
 vf.insertBefore(el('div',{class:'wide'},[el('div',{class:'line'}),selected,el('div',{class:'line'}),txt('h3','Gastos adicionales aportados'),txt('p','Los gastos sin importe quedan pendientes. Si seleccionas un vehículo se recuperan los costes de su última tasación o los presupuestos confirmados.','subtle'),costBox.node]),$('.actions',vf));
 formPanel.append(vf,result);
 const slider=$('[name=km_slider]',vf),km=$('[name=km]',vf);slider.max=600000;slider.step=1000;
 slider.addEventListener('input',()=>km.value=slider.value);km.addEventListener('input',()=>slider.value=km.value);
 for(const type of ['brands','models','generations','versions','engines'])vf.append(el('datalist',{id:'catalog-'+type}));
 async function catalog(){
  const data=await api('/api/catalog?'+new URLSearchParams({brand:$('[name=brand]',vf).value,model:$('[name=model]',vf).value,generation:$('[name=generation]',vf).value,version:$('[name=version]',vf).value}));
  for(const type of ['brands','models','generations','versions','engines'])$('#catalog-'+type,vf).replaceChildren(...(data[type]||[]).map(x=>el('option',{value:typeof x==='string'?x:x.name||x[type.slice(0,-1)]||''})));
 }
 for(const name of ['brand','model','generation','version'])$('[name='+name+']',vf).addEventListener('change',()=>catalog().catch(e=>toast(e.message,true)));
 async function calculateValuation(d,save){
  const vehicle={...d};for(const k of ['selected_listing','purchase','target_profit','discount_pct','opening_discount_pct','tax_rate','tax_base_floor','km_slider','comparable_id'])delete vehicle[k];
  const ids=$$('input[name=comparable_id]:checked',root).map(e=>Number(e.value));
  if(!ids.length){result.className='result';renderData({reliable:false,message:'No existe una tasación fiable con los datos disponibles. Selecciona comparables comprobados.'},result);return;}
  const payload={vehicle,comparable_ids:ids,costs:costBox.read(),purchase:d.purchase||0,target_profit:d.target_profit||0,discount_pct:d.discount_pct||0,opening_discount_pct:d.opening_discount_pct||0,tax_rate:(d.tax_rate||0)/100,tax_base_floor:d.tax_base_floor||0};
  const listingId=Number($('[name=selected_listing]',vf).value)||null;
  const data=save&&listingId?await api('/api/assessments','POST',{listing_id:listingId,valuation:payload}):await api('/api/valuations','POST',payload);
  result.className='result';renderData(data,result);
  result.prepend(badge(save&&listingId?'TASACIÓN GUARDADA EN LA FICHA':save?'CÁLCULO SIN VEHÍCULO ASOCIADO':'PREVISUALIZACIÓN · PULSA CALCULAR PARA GUARDAR',save&&listingId?'good':'warn'));
 }
 async function loadVehicle(id){
  if(!id){sessionStorage.removeItem('radar_vehicle_id');result.replaceChildren();return;}
  sessionStorage.setItem('radar_vehicle_id',String(id));
  const item=await api('/api/listings/'+id);
  const request=item.latest_assessment?.request?.valuation||item.latest_assessment?.request;
  const vehicle=request?.vehicle||item;
  const ignored=new Set(['selected_listing','comparable_id','km_slider','purchase','target_profit','discount_pct','opening_discount_pct','tax_rate','tax_base_floor']);
  for(const input of $$('input[name],select[name],textarea[name]',vf))if(!ignored.has(input.name)&&input.type!=='checkbox')input.value=vehicle[input.name]??'';
  $('[name=purchase]',vf).value=request?.purchase??item.price??'';
  for(const name of ['target_profit','discount_pct','opening_discount_pct','tax_base_floor'])$('[name='+name+']',vf).value=request?.[name]??0;
  $('[name=tax_rate]',vf).value=Number(request?.tax_rate||0)*100;slider.value=km.value;
  if(request?.comparable_ids)for(const input of $$('[name=comparable_id]',vf))input.checked=request.comparable_ids.map(Number).includes(Number(input.value));
  costBox.set(request?.costs||item.analysis?.costs||[]);
  result.replaceChildren();
  if(item.latest_assessment?.result){result.className='result';renderData(item.latest_assessment.result,result);result.prepend(txt('p','Última tasación guardada: '+date(item.latest_assessment.created_at),'subtle'));}
  const associated=$('[name=listing_id]',cf);if(associated)associated.value=id;
  await catalog();
 }
 $('[name=selected_listing]',vf).addEventListener('change',event=>loadVehicle(event.target.value).catch(e=>toast(e.message,true)));
 let timer;
 $('[name=target_profit]',vf).addEventListener('input',()=>{clearTimeout(timer);if(vf.checkValidity()&&$$('[name=comparable_id]:checked',vf).length)timer=setTimeout(()=>calculateValuation(read(vf),false).catch(e=>toast(e.message,true)),450);});
 const add=panel('Registrar un comparable',[txt('p','Introduce anuncios observados de procedencia legítima. La fecha y la verificación son esenciales.','subtle')]);
 const cf=form([field('source','Fuente','text','manual',{required:true}),field('external_id','Identificador fuente'),field('url','URL del comparable','url','',{required:true,wide:true}),field('brand','Marca','text','',{required:true}),field('model','Modelo','text','',{required:true}),field('generation','Generación'),field('version','Versión'),field('engine','Motor'),field('year','Año','number','',{required:true,step:1}),field('km','Kilómetros','number','',{required:true,step:1}),field('price','Precio solicitado (€)','number','',{required:true}),field('observed_at','Fecha de observación','datetime-local','',{required:true}),field('condition','Estado declarado'),field('equipment','Equipamiento'),field('province','Provincia'),field('fuel','Combustible'),field('transmission','Cambio'),field('listing_id','Vehículo asociado (opcional)','select',savedId,{items:[['','Sin asociar'],...listings.map(x=>[x.id,[x.brand,x.model,x.year].filter(Boolean).join(' ')])]}),check('verified','He comprobado los datos y la fuente')],'Guardar comparable',async d=>{await api('/api/comparables','POST',d);toast('Comparable guardado.');route();});
 add.append(cf);
 const cat=panel('Ampliar el catálogo',[txt('p','El catálogo personal no garantiza cobertura ni exactitud de versiones. Puedes escribir siempre valores manuales.','subtle'),form([field('brand','Marca','text','',{required:true}),field('model','Modelo','text','',{required:true}),field('generation','Generación'),field('version','Versión'),field('engine','Motor')],'Guardar en mi catálogo',async d=>{await api('/api/catalog','POST',d);toast('Entrada añadida al catálogo personal.');catalog();})]);
 root.append(el('div',{class:'grid two'},[formPanel,el('div',{},[add,cat])]));
 if(savedId&&listings.some(x=>String(x.id)===savedId))await loadVehicle(savedId);else await catalog();
 return root;
}
