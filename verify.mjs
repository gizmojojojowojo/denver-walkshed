import fs from 'node:fs';import assert from 'node:assert/strict';import {route,summarize,trace,linkLength} from './dist/routing.mjs';
const data=JSON.parse(fs.readFileSync(new URL('dist/corridor.json',import.meta.url)));
const base=route(data),limit=data.metadata.walkBudgetMeters;
assert.equal(data.origins.reduce((t,o)=>t+o.homes,0),6004);
const gains=data.candidates.map(c=>{
 const result=route(data,c),stats=summarize(data,base,result,limit);
 assert.equal(stats.before,1666);
 for(let i=0;i<base.dist.length;i++)assert(result.dist[i]<=base.dist[i]+1e-8);
 const o=data.origins[stats.newly[0]],walk=trace(result.parent,o.node);
 assert(data.stops.some(s=>s.node===walk.at(-1)));
 assert(walk.some((u,i)=>[c.a,c.b].includes(u)&&[c.a,c.b].includes(walk[i+1])));
 assert(linkLength(data,c)>0);return stats.gain;
});
assert.deepEqual(gains,[18,12,7]);console.log({baseline:1666,additionalHouseholds:gains});
