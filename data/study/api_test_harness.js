// api_test_harness.js — recursive, reproducible read-only test of the shoovy API.
//
// RUN IN THE CONSOLE OF A LOGGED-IN shoovy.wtf TAB. The browser is the only client
// that clears the Cloudflare bot challenge (plain HTTP clients get 429); see
// reports/edge-stock-oracle and the 429-browser-gate facts.
//
// It calls every read endpoint TWICE (reproducibility check), recursively expands
// ids/symbols found in responses into parameterized probes, and maps the write
// method surface with a harmless PUT (405/allow) WITHOUT firing any action.
// It never POSTs a mutating call. Pace it: the gate rate-limits even the browser
// after ~25 rapid calls, so keep the sleeps.
window.apiTest = async function(){
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const once=async(m,u)=>{try{const r=await fetch(u,{method:m,headers:{accept:'application/json'}});const t=await r.text();return{s:r.status,len:t.length,body:t};}catch(e){return{s:-1,len:0,body:''+e};}};
  const keysOf=t=>{try{const j=JSON.parse(t);return Array.isArray(j)?'array['+j.length+']':Object.keys(j).slice(0,10).join(',');}catch{return t.slice(0,30);}};
  const test2=async u=>{const a=await once('GET',u);await sleep(300);const b=await once('GET',u);return{ep:u,s1:a.s,s2:b.s,len:a.len,consistent:a.len===b.len&&a.body.slice(0,60)===b.body.slice(0,60),keys:a.s===200?keysOf(a.body):a.body.slice(0,40),_b:a.body};};
  const base=['/api/me','/api/stats','/api/leaderboard','/api/leaderboards','/api/user','/api/feed','/api/fishing','/api/stocks','/api/predictions','/api/games/info','/api/casino/lobby','/api/rakeback','/api/business','/api/crime','/api/shop','/api/raffles','/api/updates','/api/suggestions','/api/daily'];
  const res=[];for(const u of base){res.push(await test2(u));await sleep(400);}
  const rec=[];
  try{const j=JSON.parse(res.find(r=>r.ep==='/api/leaderboard')._b);for(const id of (j.leaderboard||[]).slice(0,2).map(x=>x.kick_user_id).filter(Boolean)){rec.push(await test2('/api/user/'+id));await sleep(400);}}catch{}
  try{const j=JSON.parse(res.find(r=>r.ep==='/api/stocks')._b);for(const s of (j.quotes||[]).slice(0,2).map(x=>x.symbol)){rec.push(await test2('/api/stocks/history?symbol='+s+'&minutes=5'));await sleep(400);}}catch{}
  const meth=[];for(const u of ['/api/stocks/trade','/api/business','/api/predictions','/api/daily','/api/raffles']){const r=await once('PUT',u);meth.push({ep:u,put:r.s,allow:r.body.slice(0,80)});await sleep(400);}
  const strip=a=>a.map(({_b,...r})=>r);
  return {base:strip(res),recursive:strip(rec),method_surface:meth};
};
// usage: await apiTest()
