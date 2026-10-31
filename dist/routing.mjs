// Multi-source Dijkstra, measured along the network to the nearest selected transit stop.
class MinHeap {
 constructor(){this.items=[]}
 push(entry){const heap=this.items;let i=heap.length;heap.push(entry);
  while(i>0){const p=(i-1)>>1;if(heap[p][0]<=entry[0])break;heap[i]=heap[p];i=p}heap[i]=entry}
 pop(){const heap=this.items,first=heap[0],tail=heap.pop();if(!heap.length)return first;
  let i=0;while(i*2+1<heap.length){let c=i*2+1;if(c+1<heap.length&&heap[c+1][0]<heap[c][0])c++;
   if(heap[c][0]>=tail[0])break;heap[i]=heap[c];i=c}heap[i]=tail;return first}
}
export function linkLength(data,c){
 const [x,y]=data.nodes[c.a],[u,v]=data.nodes[c.b];return c.lengthMeters??Math.hypot(x-u,y-v);
}
export function route(data,candidate=null){
 const adj=data.nodes.map(()=>[]);function connect(a,b,w){adj[a].push([b,w]);adj[b].push([a,w])}
 for(const [a,b,w] of data.edges)connect(a,b,w);
 if(candidate)connect(candidate.a,candidate.b,linkLength(data,candidate));
 const dist=Array(adj.length).fill(Infinity),parent=Array(adj.length).fill(-1),heap=new MinHeap();
 for(const {node} of data.stops){dist[node]=0;heap.push([0,node])}
 while(heap.items.length){const [d,u]=heap.pop();if(d!==dist[u])continue;for(const [v,w] of adj[u]){const next=d+w;if(next<dist[v]){dist[v]=next;parent[v]=u;heap.push([next,v])}}}
 return {dist,parent};
}
export function trace(parent,node){const path=[];for(let u=node;u!==-1;u=parent[u])path.push(u);return path}
export function summarize(data,baseline,scenario,limit){
 let before=0,after=0;const newly=[];
 for(const [i,o] of data.origins.entries()){const a=baseline.dist[o.node]+(o.offset||0),b=scenario.dist[o.node]+(o.offset||0);
  if(a<=limit)before+=o.homes;if(b<=limit)after+=o.homes;if(a>limit&&b<=limit&&o.homes>0)newly.push(i)}
 return {before,after,gain:after-before,newly};
}
