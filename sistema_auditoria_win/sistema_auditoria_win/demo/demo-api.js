/* Servidor simulado en el navegador para la demo (datos incrustados en window.DEMO). Solo lectura. */
(function(){
const D=window.DEMO,CR=D.criterios,PL=D.pilares,PK=Object.keys(PL),MIN=5;
const J=(o,s=200)=>new Response(JSON.stringify(o),{status:s,headers:{"Content-Type":"application/json"}});
const niv=n=>n==null?null:n<70?"Deficiente":n<85?"Aceptable":"Excelente",r1=x=>Math.round(x*10)/10;
const avg=a=>a.length?a.reduce((x,y)=>x+y,0)/a.length:null,V={S:"SI",N:"NO",A:"No Aplica"};
let SES=null;const VAL=D.validaciones.map(x=>({...x}));const fin=v=>v.decision||v.estado;
const AS={};D.asesores.forEach(a=>AS[a.id]=a);
const rows=D.filas.map(f=>({id:f[0],ll:f[1],f:f[2],as:f[3],cam:f[4],v:f[5],nota:f[6],p:f.slice(7,11),c:f[11]}));
const lunes=s=>{const d=new Date(s+"T00:00:00Z");d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));return d.toISOString().slice(0,10)};
const supN=r=>AS[r.as].supervisor;
function filtrar(q){return rows.filter(r=>(q.ventas==="0"?true:r.v===1)&&(!q.desde||r.f>=q.desde)&&(!q.hasta||r.f<=q.hasta)&&(!q.campana||r.cam===q.campana)&&(!q.supervisor||supN(r)===q.supervisor)&&(!q.asesor||AS[r.as].nombre===q.asesor))}
function pilares(rs){return PK.map((k,i)=>({pilar:k,modelo:PL[k].modelo,peso:Math.round(PL[k].peso*100),cumplimiento:r1(avg(rs.map(r=>r.p[i]))||0)}))}
function pct(rs,fn){return rs.length?r1(100*rs.filter(fn).length/rs.length):0}
function crit(rs,gl){const o=[];CR.forEach((c,i)=>{let no=0,ap=0;rs.forEach(r=>{const x=r.c[i];if(x==="N")no++;if(x==="N"||x==="S")ap++});o.push({id:c.id,nombre:c.nombre,pilar:c.pilar,no,aplicables:ap,pct_no:ap?r1(100*no/ap):0,equipo:gl?r1(gl[i]):0})});return o}
function dash(q){const rs=filtrar(q),n=rs.length,g=k=>rs.filter(r=>niv(r.nota)===k).length;
 const gr=(kf,nf)=>{const m={};rs.forEach(r=>(m[kf(r)]=m[kf(r)]||[]).push(r));return Object.entries(m).map(([k,v])=>nf(k,v))};
 const cs=crit(rs).sort((a,b)=>b.pct_no-a.pct_no);
 return{n,nota:r1(avg(rs.map(r=>r.nota))||0),pct_deficiente:pct(rs,r=>r.nota<70),pct_aceptable:pct(rs,r=>r.nota>=70&&r.nota<85),pct_excelente:pct(rs,r=>r.nota>=85),
  quiebres_prom:Math.round(100*(avg(rs.map(r=>[...r.c].filter(x=>x==="N").length))||0))/100,pendientes:0,pendientes_respaldo:0,pilares:pilares(rs),
  semanal:gr(r=>lunes(r.f),(k,v)=>({semana:k,nota:r1(avg(v.map(r=>r.nota))),n:v.length})).sort((a,b)=>a.semana<b.semana?-1:1),
  supervisores:gr(supN,(k,v)=>({nombre:k,nota:r1(avg(v.map(r=>r.nota))),n:v.length})).sort((a,b)=>a.nota-b.nota),
  asesores:gr(r=>r.as,(k,v)=>({id:+k,nombre:AS[k].nombre,nota:r1(avg(v.map(r=>r.nota))),n:v.length,deficientes:v.filter(r=>r.nota<70).length,muestra_pequena:v.length<MIN})).sort((a,b)=>a.nota-b.nota).slice(0,10),
  criterios:cs,min_muestra:MIN,bot:{n_revisadas:0}}}
function asesores(q){const ids=Object.keys(AS).map(Number);let L=ids.map(id=>{const a=AS[id],all=rows.filter(r=>r.as===id),vs=all.filter(r=>r.v===1),nota=avg(vs.map(r=>r.nota));
 return{id,nombre:a.nombre,dni:a.dni,supervisor:a.supervisor,campana:all[0]&&all[0].cam,camps:[...new Set(all.map(r=>r.cam))],llamadas:all.length,n:vs.length,nota:nota==null?null:r1(nota),d:vs.filter(r=>r.nota<70).length,ultima:all.map(r=>r.f).sort().pop(),pend:0,nivel:niv(nota),muestra_pequena:vs.length<MIN}});
 L=L.filter(a=>(!q.q||a.nombre.toLowerCase().includes(q.q.toLowerCase()))&&(!q.supervisor||a.supervisor===q.supervisor)&&(!q.campana||a.camps.includes(q.campana)));
 const o=q.orden;L.sort(o==="nota_asc"?(a,b)=>a.nota-b.nota:o==="nota_desc"?(a,b)=>b.nota-a.nota:o==="def"?(a,b)=>b.d-a.d||a.nota-b.nota:(a,b)=>a.nombre<b.nombre?-1:1);return{total:L.length,asesores:L,min_muestra:MIN}}
function perfil(id){const a=AS[id];if(!a)return null;const all=rows.filter(r=>r.as===id),vs=all.filter(r=>r.v===1),n=vs.length,eq=rows.filter(r=>r.v===1),gl=crit(eq).map(c=>c.pct_no),nota=avg(vs.map(r=>r.nota));
 const cs=crit(vs,gl).sort((x,y)=>y.no-x.no||y.pct_no-x.pct_no);
 return{asesor:{id,nombre:a.nombre,dni:a.dni,supervisor:a.supervisor},n,nota:n?r1(nota):null,equipo:r1(avg(eq.map(r=>r.nota))),pct_deficiente:pct(vs,r=>r.nota<70),pct_aceptable:pct(vs,r=>r.nota>=70&&r.nota<85),pct_excelente:pct(vs,r=>r.nota>=85),nivel:niv(nota),
  pilares:pilares(vs),evolucion:vs.slice().sort((x,y)=>x.f<y.f?-1:x.f>y.f?1:x.id-y.id).map(r=>({id:r.id,fecha:r.f,nota:r1(r.nota),nivel:niv(r.nota)})),criterios:cs,coaching:cs.filter(c=>c.no>0).slice(0,3),
  historial:all.slice().sort((x,y)=>x.f<y.f?1:x.f>y.f?-1:y.id-x.id).map(r=>({id:r.id,llamada:r.ll,fecha:r.f,venta:r.v,nota:r1(r.nota),nivel:niv(r.nota),estado:"VALIDADA",ruta:null,nota_bot:null,pauta:null})),muestra_pequena:n<MIN,min_muestra:MIN}}
function lista(q){let L=rows.filter(r=>(q.ventas==="1"?r.v===1:true)&&(!q.estado||q.estado==="VALIDADA")&&(!q.q||r.ll.includes(q.q)||AS[r.as].nombre.toLowerCase().includes(q.q.toLowerCase()))).sort((a,b)=>b.id-a.id);
 const lim=+q.limite||50,off=+q.desplazamiento||0;return{total:L.length,filas:L.slice(off,off+lim).map(r=>({id:r.id,llamada:r.ll,fecha:r.f,asesor:AS[r.as].nombre,campana:r.cam,supervisor:supN(r),venta:r.v,nota:r1(r.nota),nivel:niv(r.nota),nota_bot:null,nivel_bot:null,estado:"VALIDADA",origen:"historico",ruta:null}))}}
function detalle(id){const r=rows.find(x=>x.id===id);if(!r)return null;return{id_auditoria:r.id,id_llamada:r.ll,fecha_llamada:r.f,asesor:AS[r.as].nombre,campana:r.cam,supervisor:supN(r),venta_concretada:r.v,estado:"VALIDADA",origen:"historico",nota:r1(r.nota),nivel:niv(r.nota),nota_bot:null,nivel_bot:null,ruta:null,motivos_ruta:[],regla:"vigente",
  criterios:CR.map((c,i)=>({id_criterio:c.id,nombre:c.nombre,pilar:c.pilar,valor_bot:null,confianza_bot:null,valor_final:V[r.c[i]]||"No Aplica",observacion:null,evidencia:null})),historial:[],transcripcion:null,descripcion:null,pauta:[],pauta_veredicto:null,pauta_pct:null}}
function calcular(v,regla){const o={},q={};let nota=0;PK.forEach(p=>{const ids=CR.filter(c=>c.pilar===p).map(c=>c.id),no=ids.filter(i=>v[i]==="NO").length,den=regla==="alternativa"?ids.filter(i=>v[i]!=="No Aplica").length:ids.length;o[p]=den?100*(1-no/den):100;q[p]=no;nota+=PL[p].peso*o[p]});
 return{auditable:true,pilares:o,nota,nivel:niv(nota),quiebres:q}}
const NOSE=J({error:"Esta es una demo de solo lectura. Guardar y revisar auditorías está disponible en la versión desplegada."},400);
window.fetch=async(path,opt)=>{const u=new URL(path,"http://x"),p=u.pathname,q=Object.fromEntries(u.searchParams),post=opt&&opt.method==="POST";let b={};try{b=post&&opt.body?JSON.parse(opt.body):{}}catch(e){}
 await new Promise(r=>setTimeout(r,60));let m;
 if(p==="/api/login"){const u=(b.usuario||"").trim().toUpperCase(),c=(b.clave||"").trim();
  if(u==="SUPERVISOR"&&c==="60431749"){SES={usuario:"SUPERVISOR",rol:"admin",id_asesor:null};return J(SES)}
  const a=D.asesores.find(x=>x.nombre.toUpperCase()===u);if(a&&c.toUpperCase()===a.nombre.toUpperCase()){SES={usuario:a.nombre,rol:"asesor",id_asesor:a.id};return J(SES)}
  return J({error:"Usuario o clave incorrectos"},401)}
 if(p==="/api/logout"){SES=null;return J({ok:true})}
 if(p==="/api/yo")return J(SES?{auth:true,...SES}:{auth:true,usuario:null,rol:null,id_asesor:null});
 if(!SES)return J({error:"Inicia sesión para continuar"},401);
 if(SES.rol==="asesor"&&!["/api/meta","/api/validar","/api/pauta","/api/ejemplos-ventas","/api/validaciones",`/api/asesor/${SES.id_asesor}`].includes(p)&&!/^\/api\/validacion\/\d+$/.test(p))return J({error:"No tienes acceso a esta sección"},403);
 if(p==="/api/ejemplos-ventas")return J(D.ventas);
 if(p==="/api/validaciones"){let L=VAL.filter(v=>(!q.estado||fin(v)===q.estado)&&(SES.rol!=="asesor"||v.id_asesor===SES.id_asesor));return J(L.slice().sort((a,c)=>c.id-a.id).map(v=>({id:v.id,id_asesor:v.id_asesor,asesor:AS[v.id_asesor].nombre,fecha:v.fecha,cliente:v.cliente,estado:v.estado,decision:v.decision||null,final:fin(v),pct_contrato:v.resultado.pct_contrato,claridad:v.resultado.claridad,pct_datos:v.resultado.pct_datos})))}
 if(m=p.match(/^\/api\/validacion\/(\d+)$/)){const v=VAL.find(x=>x.id===+m[1]);if(!v||(SES.rol==="asesor"&&v.id_asesor!==SES.id_asesor))return J({error:"Venta no encontrada"},404);return J({id_validacion:v.id,asesor:AS[v.id_asesor].nombre,fecha:v.fecha,cliente:v.cliente,estado:v.estado,decision:v.decision||null,revisado_por:v.revisado_por||null,motivo_decision:v.motivo||null,transcripcion:v.transcripcion,resultado:v.resultado,final:fin(v)})}
 if(m=p.match(/^\/api\/validacion\/(\d+)\/decidir$/)){const v=VAL.find(x=>x.id===+m[1]);if(!v||SES.rol!=="admin")return J({error:"No permitido"},403);v.decision=b.decision;v.revisado_por="SUPERVISOR";v.motivo=b.motivo||"";return J({id:v.id,final:v.decision})}
 if(p==="/api/validar"){const k=(b.transcripcion||"").trim(),e=D.ventas.find(x=>x.transcripcion.trim()===k);if(!(b.plantilla||"").trim())return J({error:"Falta la plantilla del cliente (nombre, DNI, nacimiento, correo, teléfono, dirección e internet)"},400);
  if(!e)return J({error:"En la demo solo se pueden validar las ventas de ejemplo: elígela en «Probar con una venta de ejemplo»."},400);
  const res=D.resultados[e.id],id=Math.max(...VAL.map(v=>v.id))+1;VAL.push({id,id_asesor:SES.rol==="asesor"?SES.id_asesor:D.asesores[0].id,fecha:new Date().toISOString().slice(0,16).replace("T"," "),cliente:res.cliente,estado:res.estado,transcripcion:e.transcripcion,resultado:res});return J({...res,id})}
 if(p==="/api/meta")return J({criterios:CR,valores:["SI","NO","No Aplica","Sin contacto"],pilares:PL,umbrales:{deficiente:70,excelente:85,margen:5,tau:.6},asr:false,filtros:D.filtros});
 if(p==="/api/resumen")return J({asesores:60,ventas:rows.filter(r=>r.v).length,nota:dash({ventas:"1"}).nota,auditorias:rows.length,pendientes:0,clausulas:D.pauta.length,pauta_ejemplo:false,validaciones:{enviadas:VAL.length,aprobadas:VAL.filter(v=>fin(v)==="APROBADO").length,rechazadas:VAL.filter(v=>fin(v)==="RECHAZADO").length,por_revisar:VAL.filter(v=>v.estado==="OBSERVADO"&&!v.decision).length}});
 if(p==="/api/dashboard")return J(dash(q));if(p==="/api/asesores")return J(asesores(q));if(p==="/api/auditorias")return J(lista(q));if(p==="/api/cola")return J([]);
 if(p==="/api/ejemplos")return J(D.ejemplos);if(p==="/api/pauta"&&!post)return J({clausulas:D.pauta,ejemplo:false});
 if(m=p.match(/^\/api\/asesor\/(\d+)$/)){const x=perfil(+m[1]);return x?J(x):J({error:"Asesor no encontrado"},404)}
 if(m=p.match(/^\/api\/auditoria\/(\d+)$/)){const x=detalle(+m[1]);return x?J(x):J({error:"No encontrada"},404)}
 if(p==="/api/calcular")return J(calcular(b.valores,b.regla));
 if(p==="/api/auditar"||p==="/api/pauta/probar"){const k=(b.transcripcion||"").trim(),e=D.auditar[k];if(!e)return J({error:"En la demo solo se pueden analizar los ejemplos precargados (elige uno en «Cargar un ejemplo»)."},400);return J(p==="/api/auditar"?e:e.pauta||{clausulas:[],veredicto:"—",pct:0})}
 return NOSE}})();
