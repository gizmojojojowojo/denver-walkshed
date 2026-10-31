import {route,trace,summarize} from './routing.mjs';
const el=id=>document.getElementById(id),txt=(id,v)=>el(id).textContent=v,fmt=n=>n.toLocaleString('en-US');
const svgNS='http://www.w3.org/2000/svg';
function svg(tag,attrs,content){const n=document.createElementNS(svgNS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(content)n.textContent=content;return n}
async function start(){
 const r=await fetch('./corridor.json');if(!r.ok)throw Error('The corridor snapshot could not load.');const data=await r.json(),m=data.metadata;
 const baseline=route(data),routes=data.candidates.map(c=>route(data,c)),speed=m.speedMps;
 let selected=0,origin=0,stats=[],focus=true;
 const nodes=data.nodes;const xs=nodes.map(p=>p[0]),ys=nodes.map(p=>p[1]);const left=Math.min(...xs)-50,right=Math.max(...xs)+50,bottom=Math.min(...ys)-50,top=Math.max(...ys)+50;
 const map=el('map');map.setAttribute('viewBox',[left,-top,right-left,top-bottom].join(' '));
 const xy=i=>[nodes[i][0],-nodes[i][1]].join(' '),line=ids=>'M'+ids.map(xy).join('L');
 const base=svg('path',{d:data.edges.map(([a,b])=>line([a,b])).join(''),fill:'none',stroke:'#b1bdb2','stroke-width':3});map.append(base);
 const overlay=svg('g',{});map.append(overlay);
 function time(d){return Number.isFinite(d)?(d/speed/60).toFixed(1)+' min':'No mapped route'}
 function updateOrigin(){const o=data.origins[origin],a=baseline.dist[o.node]+(o.offset||0),b=routes[selected].dist[o.node]+(o.offset||0);txt('routeinfo',time(a)+' before → '+time(b)+' after');draw()}
 function draw(){
  overlay.replaceChildren();const c=data.candidates[selected],s=stats[selected],o=data.origins[origin];
  for(const i of s.newly){const h=data.origins[i],p=h.point||nodes[h.node];overlay.append(svg('path',{d:'M'+p[0]+' '+(-p[1]-9)+'l9 9 -9 9 -9 -9Z',fill:'#d37829',stroke:'#fff','stroke-width':2}))}
  for(const [r,color,dash,w] of [[baseline,'#a9472c','12 8',8],[routes[selected],'#007d68','',5]]){
   if(Number.isFinite(r.dist[o.node]))overlay.append(svg('path',{d:line(trace(r.parent,o.node)),fill:'none',stroke:color,'stroke-width':w,'stroke-dasharray':dash,'stroke-linejoin':'round'}));
  }
  overlay.append(svg('path',{d:line([c.a,c.b]),stroke:'#fff','stroke-width':15}),svg('path',{d:line([c.a,c.b]),stroke:'#e57618','stroke-width':8}));
  const start=o.point||nodes[o.node];
  let view=[left,-top,right-left,top-bottom];
  if(focus){
   const visible=[start,nodes[c.a],nodes[c.b],...trace(baseline.parent,o.node).map(i=>nodes[i]),...trace(routes[selected].parent,o.node).map(i=>nodes[i])];
   const xx=visible.map(p=>p[0]),yy=visible.map(p=>p[1]);const w=Math.max(...xx)-Math.min(...xx),h=Math.max(...yy)-Math.min(...yy);
   const pad=Math.max(60,Math.max(w,h)*0.12);view=[Math.min(...xx)-pad,-Math.max(...yy)-pad,w+2*pad,h+2*pad];
  }
  map.setAttribute('viewBox',view.join(' '));el('extent').setAttribute('aria-pressed',String(focus));txt('extent',focus?'Show full corridor':'Focus on route');
  if(o.point)overlay.append(svg('path',{d:'M'+start[0]+' '+(-start[1])+'L'+xy(o.node),stroke:'#205b52','stroke-width':4,'stroke-dasharray':'4 4'}));
  overlay.append(svg('circle',{cx:start[0],cy:-start[1],r:12,fill:'#fff',stroke:'#005d4a','stroke-width':5}));
  data.stops.forEach(({node,name},i)=>{const [x,y]=nodes[node],g=svg('g',{});g.append(svg('title',{},name),svg('circle',{cx:x,cy:-y,r:10,fill:'#193c4e',stroke:'#fff','stroke-width':3}),svg('text',{x,y:-y+(i%2?47:-26),'text-anchor':'middle','font-size':27,'font-family':'system-ui','font-weight':650,fill:'#183949',stroke:'#edf0e5','stroke-width':7,'paint-order':'stroke'},name.replace(/^.*? & /,'')));overlay.append(g)});
  const scaleX=view[0]+25,scaleY=view[1]+view[3]-25;overlay.append(svg('path',{d:'M'+scaleX+' '+scaleY+'h250',stroke:'#455b5a','stroke-width':5}),svg('text',{x:scaleX,y:scaleY-12,'font-size':29,fill:'#455b5a'},'250 m'));
 }
 function update(){
  const budget=Number(el('budget').value),limit=budget*60*speed;stats=routes.map(r=>summarize(data,baseline,r,limit));const s=stats[selected],c=data.candidates[selected];
  el('scenarios').replaceChildren(...data.candidates.map((item,i)=>{const b=document.createElement('button');b.setAttribute('aria-pressed',String(i===selected));b.innerHTML='<b></b><span></span><small></small>';b.firstChild.textContent='0'+(i+1);b.children[1].textContent=item.name;b.lastChild.textContent='+'+fmt(stats[i].gain);b.onclick=()=>{selected=i;update()};return b}));
  txt('description',c.description);txt('gain','+'+fmt(s.gain));txt('counts',fmt(s.before)+' baseline → '+fmt(s.after)+' within '+budget+' minutes.');
  const ids=data.origins.map((_,i)=>i).filter(i=>data.origins[i].homes>0);const gain=i=>baseline.dist[data.origins[i].node]-routes[selected].dist[data.origins[i].node];const newly=new Set(s.newly);
  ids.sort((i,j)=>Number(newly.has(j))-Number(newly.has(i))||(gain(j)||0)-(gain(i)||0)||i-j);origin=ids[0];
  el('origin').replaceChildren(...ids.map(i=>new Option((newly.has(i)?'◆ ':'')+data.origins[i].label+' · '+data.origins[i].homes+' households',i)));updateOrigin();
 }
 el('extent').onclick=()=>{focus=!focus;draw()};el('origin').onchange=()=>{origin=Number(el('origin').value);updateOrigin()};el('budget').onchange=update;
 for(const [i,source] of m.sourceLinks.entries()){const a=document.createElement('a');a.href=source.url;a.textContent=source.name;el('sources').append(i?' · ':'Sources: ',a)}
 update();
}
start().catch(e=>{txt('gain','—');txt('description',e.message)});
