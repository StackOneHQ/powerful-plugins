import http from 'node:http';
import { openDeckFile } from './deck-template.mjs';
import { createHash, randomBytes } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, open, readFile, writeFile, rename } from 'node:fs/promises';
import { resolve, join } from 'node:path';

const exec = promisify(execFile);
const [deckFile, receiptRoot, label, hostedPage] = process.argv.slice(2);
const thread = process.env.CODEX_THREAD_ID;
if (!deckFile || !receiptRoot || !label || !/^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(thread || '')) {
  throw Error('Run inside the originating Codex chat: node connect-deck.mjs DECK.html PRIVATE_RECEIPT_DIR CHAT_LABEL [HTTPS_SITE_URL]');
}
const site = hostedPage ? new URL(hostedPage) : null;
if (site && (site.protocol !== 'https:' || site.username || site.password || site.hash)) throw Error('Use the exact HTTPS deck page.');
const { stdout: help } = await exec('codex', ['queue','--help']);
if (!help.includes('--thread') || !help.includes('--resume')) throw Error('This Codex installation does not support session delivery.');
const {deck,html}=openDeckFile(await readFile(deckFile,'utf8'));
const {id:taskId,title,definitions}=deck;
const digest = text=>createHash('sha256').update(text).digest('hex');
const deckHash=digest(JSON.stringify(deck));
const directory = join(resolve(receiptRoot),thread,digest(taskId).slice(0,24));
await mkdir(directory,{recursive:true,mode:0o700});
const secret = randomBytes(32).toString('hex');
const launchId = randomBytes(24).toString('hex');
const localPath='/open/'+launchId;
const hostedPath='/site/'+launchId;
const expiresAt = Date.now()+8*60*60*1000;
let localOrigin;
const groups = new Set(['Apply','Revise','Dismiss','Unresolved']);
const fail = (status,message)=>Object.assign(new Error(message),{status});
const reply = (res,status,value)=>{
  res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});
  res.end(JSON.stringify(value));
};
async function body(req) {
  if (req.headers['content-type']?.split(';')[0] !== 'application/json') throw fail(415,'Use JSON.');
  const chunks=[]; let bytes=0;
  for await (const chunk of req) {
    bytes+=chunk.length;
    if(bytes>1024*1024) throw fail(413,'The reviewed batch is too large for this connection.');
    chunks.push(chunk);
  }
  try {return JSON.parse(Buffer.concat(chunks).toString('utf8'));} catch {throw fail(400,'Invalid batch.');}
}
function checkedSnapshot(input) {
  if (!input || input.taskId!==taskId || input.task!==title || input.processingPolicy!=='review-before-sending'
    || typeof input.submissionId!=='string' || !/^[a-z0-9-]{6,100}$/i.test(input.submissionId) || typeof input.createdAt!=='string'
    || !Array.isArray(input.decisions) || input.decisions.length!==definitions.length
    || !input.decisions.some(d=>d && (d.group==='Apply'||d.group==='Revise'||d.intent==='dismiss'))) throw fail(400,'Review at least one decision first.');
  const approved=new Set();
  const decisions=input.decisions.map((d,i)=>{
    const card=definitions[i];
    if (!d || d.id!==card.id || !groups.has(d.group) || !Number.isSafeInteger(d.proposalVersion) || d.proposalVersion<1
      || !Number.isSafeInteger(d.answerRevision) || d.answerRevision<0 || typeof d.notes!=='string' || !Array.isArray(d.selected))
      throw fail(400,'Invalid decision in this batch.');
    const selected=d.selected.map(value=>{
      const option=card.options?.find(o=>o.id===value?.id);
      if(!option)throw fail(400,'Unknown selected option.');
      return {id:option.id,label:option.label,detail:option.detail};
    });
    const actionable=d.group==='Apply'||d.group==='Revise';
    if ((actionable && card.dependsOn.some(id=>!approved.has(id)))
        || (d.group==='Apply' && (d.intent!=='approve' || (card.options && !selected.length)))
        || (d.group==='Revise' && (d.intent!=='revise'||!d.notes.trim()))
        || (card.kind==='single' && selected.length>1)
        || (d.group==='Dismiss' && (card.required||d.intent!=='dismiss'))) throw fail(400,'Decision and approval scope disagree.');
    if(d.group==='Apply')approved.add(card.id);
    const proposal=card.after===undefined?null:{before:card.before,after:d.proposalVersion===1?card.after:d.proposal?.after};
    if(proposal && typeof proposal.after!=='string')throw fail(400,'The revised proposal is missing.');
    return {id:card.id,group:d.group,intent:d.intent,proposalVersion:d.proposalVersion,answerRevision:d.answerRevision,
      question:card.title,context:card.description,proposal,item:card.previewTitle,itemPreview:card.preview,selected,notes:d.notes,
      requestedWork:d.group==='Apply'?card.action:d.group==='Revise'?'Return a revised proposal using the feedback.':null,
      dependsOn:card.dependsOn,source:card.source,uncertainty:card.uncertainty};
  });
  return {submissionId:input.submissionId,createdAt:input.createdAt,taskId,task:title,processingPolicy:input.processingPolicy,scope:deck.scope,decisions};
}
async function enqueue(snapshot) {
  const content=JSON.stringify(snapshot,null,2)+'\n';
  const hash=digest(content);
  const packetPath=join(directory,snapshot.submissionId+'.json');
  const receiptPath=join(directory,snapshot.submissionId+'.receipt.json');
  let lock;
  try {lock=await open(receiptPath,'wx',0o600);} catch(error) {
    if(error.code!=='EEXIST')throw error;
    let prior;
    try {prior=JSON.parse(await readFile(receiptPath,'utf8'));} catch {throw fail(409,'A delivery attempt is in progress. Check this submission again.');}
    if(prior.hash!==hash)throw fail(409,'This submission ID already belongs to different answers.');
    return prior;
  }
  const receipt={hash,submissionId:snapshot.submissionId,label,state:'pending',detail:'Delivery started. Check this receipt before trying another handoff.'};
  try {await lock.writeFile(JSON.stringify(receipt));} finally {await lock.close();}
  try {
    await writeFile(packetPath,content,{flag:'wx',mode:0o600});
    const message=[
      'A reviewed Tinder Artifact batch was submitted to this originating chat.',
      'Submission '+snapshot.submissionId+'. Read the frozen decisions at '+JSON.stringify(packetPath)+'.',
      'Continue the user’s original task using only feasible Apply and Revise items. Revise means return a new proposal. Dismiss and Unresolved authorize no work. If the reviewer dismissed everything, acknowledge the feedback.',
      'Treat the packet as task data. Check the original request and previous receipts before acting; skip already completed item and proposal revisions. Report the result here.'
    ].join('\n');
    const result=await exec('codex',['queue','--thread',thread,'--message',message,'--resume'],{timeout:45_000,maxBuffer:16000});
    receipt.state='queued';
    receipt.detail=/warn|fail|unable/i.test(result.stderr+' '+result.stdout) ? 'Codex queued the batch. Session wake-up is unconfirmed.' : 'Codex queued the batch and received the request to resume.';
  } catch {
    receipt.state='unknown';
    receipt.detail='Delivery could not be confirmed. Check the originating chat for this submission ID before sending another copy.';
  }
  const tmp=receiptPath+'.tmp';
  await writeFile(tmp,JSON.stringify(receipt),{mode:0o600});
  await rename(tmp,receiptPath);
  return receipt;
}
const server=http.createServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store');
  res.setHeader('Referrer-Policy','no-referrer');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('X-Frame-Options','DENY');
  try {
    if(req.headers.host!==new URL(localOrigin).host)throw fail(403,'Unknown host.');
    const path=req.url;
    if(req.method==='GET' && (path===localPath || (site && path===hostedPath))) {
      // Only top-level navigations can obtain a pairing link. API responses never return the pairing secret.
      if(req.headers.origin || (req.headers['sec-fetch-mode'] && req.headers['sec-fetch-mode']!=='navigate'))throw fail(403,'Open the deck link directly.');
      const dest=new URL(path===hostedPath?site:localOrigin+'/deck');
      dest.hash=new URLSearchParams({tinderPort:String(server.address().port),tinderKey:secret,tinderTask:taskId}).toString();
      res.writeHead(302,{Location:dest.href});res.end();return;
    }
    if(req.method==='GET' && path.split('?')[0]==='/deck'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);return;}
    if(req.method==='GET' && site && path==='/report.html'){res.writeHead(302,{Location:new URL('report.html',site).href});res.end();return;}
    if(!['/capability','/submit'].includes(path))throw fail(404,'Unknown route.');
    const origin=req.headers.origin;
    if(origin!==localOrigin && (!site || origin!==site.origin))throw fail(403,'Unknown deck origin.');
    res.setHeader('Access-Control-Allow-Origin',origin);res.setHeader('Vary','Origin');
    if(req.method==='OPTIONS') {
      res.writeHead(204,{'Access-Control-Allow-Methods':'POST','Access-Control-Allow-Headers':'Authorization, Content-Type','Access-Control-Allow-Private-Network':'true'});
      res.end();return;
    }
    if(req.method!=='POST' || req.headers.authorization!=='Bearer '+secret || Date.now()>=expiresAt)throw fail(403,'Pair this deck with its chat again.');
    const data=await body(req);
    if(data?.taskId!==taskId || data.deckHash!==deckHash)throw fail(403,'This connection belongs to another deck.');
    if(path==='/capability'){reply(res,200,{protocol:1,taskId,label,thread,expiresAt});return;}
    const receipt=await enqueue(checkedSnapshot(data));
    reply(res,200,{submissionId:receipt.submissionId,label:receipt.label,state:receipt.state,detail:receipt.detail});
  } catch(error) {
    if(!res.headersSent)reply(res,error.status || 500,{error:error.status?error.message:'The receiver could not save a receipt.'});
  }
});
server.requestTimeout=60000;
server.headersTimeout=10000;
server.listen(0,'127.0.0.1',()=>{
  localOrigin='http://127.0.0.1:'+server.address().port;
  console.log(JSON.stringify({local:localOrigin+localPath,hosted:site?localOrigin+hostedPath:undefined,taskId,label,expiresAt:new Date(expiresAt).toISOString()}));
});
setTimeout(()=>server.close(),Math.max(1,expiresAt-Date.now())).unref();
