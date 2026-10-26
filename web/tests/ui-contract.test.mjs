import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');
function implementation(name) {
  const match = new RegExp(`\\n  (?:async )?function ${name}\\(`).exec(source);
  assert.ok(match, `Implementation function ${name} exists`);
  const start = match.index + 1;
  const next = /\n  (?:async )?function /g;
  next.lastIndex = start + match[0].length;
  const end = next.exec(source)?.index ?? source.length;
  return source.slice(start, end).trim();
}

// Run the shipped selection function. Cases exercise orientation and touch input,
// not just static media-query strings.
test('automatic selection chooses each intended workspace, including phone landscape and iPad rotations', () => {
  const cases = [
    [402, 874, true, 'phone'], [874, 402, true, 'phone'],
    [820, 1180, true, 'tablet'], [1180, 820, true, 'tablet'],
    [1366, 768, false, 'desktop'], [1440, 900, false, 'desktop'],
    [1920, 1080, false, 'wide'], [3440, 1440, false, 'ultrawide']
  ];
  for (const [width, height, touch, expected] of cases) {
    const context = vm.createContext({window: {innerWidth: width, innerHeight: height}, navigator: {userAgent: ''}, matchMedia: () => ({matches: touch})});
    vm.runInContext(implementation('autoLayout'), context);
    assert.equal(context.autoLayout(), expected, `${width}×${height}`);
  }
});

// Minimal tree adapter: only the append/move/query behavior used by the actual
// composition function. This verifies different parentage with one shared set
// of live components; it is not a browser rendering test.
test('five profiles move the same controls into distinct arrangements without copies', () => {
  const registry = new Map(); const all = [];
  class Node {
    constructor(tag='div', className='') { this.tagName=tag; this.className=className; this.children=[]; this.dataset={}; this.attributes={}; this.parentNode=null; this.open=false; this.hidden=false; all.push(this); }
    set id(value) { this._id=value; registry.set(value,this); }
    get id() { return this._id; }
    append(...nodes) { for (const node of nodes) { if (node.parentNode) node.parentNode.children.splice(node.parentNode.children.indexOf(node),1); node.parentNode=this; this.children.push(node); } }
    prepend(...nodes) { this.append(...nodes); this.children.unshift(...this.children.splice(-nodes.length)); }
    close() { this.open=false; }
    replaceChildren(...nodes) { this.children.forEach(child => { child.parentNode=null; }); this.children=[]; this.append(...nodes); }
    setAttribute(name,value) { this.attributes[name]=value; }
  }
  const get = selector => { const id=selector.slice(1); if (!registry.has(id)) { const node=new Node(); node.id=id; } return registry.get(id); };
  for (const id of ['layout-host','component-parking','evidence-dialog','desktop-controls','phone-actions','phone-dock','layout-select','layout-caption','layout-description','layout-preview','inspection-title']) get('#'+id);
  const components = Object.fromEntries(['project','architect','lead','routing','workers','outcome','activity','inspection','more','evidence','controls'].map(name => [name,new Node('div',name)]));
  const context = vm.createContext({S:{layout:'desktop',orientation:'portrait',preferenceLayout:'desktop',phoneTab:'work',evidenceView:'overview'}, document:{documentElement:{dataset:{}}}, innerWidth:1440,innerHeight:900, COMPONENTS:components, LAYOUT_NAMES:{phone:'iPhone',tablet:'iPad',desktop:'Desktop',wide:'Widescreen',ultrawide:'Ultrawide'},LAYOUT_DESCRIPTIONS:{},$:get,el:(tag,classes)=>new Node(tag,classes),setText:()=>{},autoLayout:()=> 'desktop',activatePhoneTab:()=>{},updateDockOverview:()=>{}});
  vm.runInContext(implementation('lane')+'\n'+implementation('composeLayout')+'\n'+implementation('restoreMenuContent'),context);
  const checkUnique = () => { for (const component of Object.values(components)) assert.equal(all.reduce((count,node)=>count+node.children.filter(child=>child===component).length,0),1); };
  for (const profile of ['phone','tablet','desktop','wide','ultrawide','phone']) {
    context.S.preferenceLayout=profile; context.composeLayout(true); checkUnique();
    const host=get('#layout-host');
    if (profile==='phone') { assert.equal(host.children.length,4); assert.equal(components.architect.parentNode.dataset.phonePanel,'team'); assert.equal(components.controls.parentNode,get('#phone-actions')); }
    if (profile==='tablet') { assert.equal(host.children.length,3); assert.match(components.project.parentNode.className,/tablet-project/); assert.equal(components.workers.parentNode,components.architect.parentNode); }
    if (profile==='desktop') { assert.equal(host.children.length,3); assert.notEqual(components.architect.parentNode,components.workers.parentNode); assert.match(components.activity.parentNode.className,/desktop-activity/); }
    if (profile==='wide') { assert.equal(host.children.length,3); assert.equal(components.inspection.parentNode,components.architect.parentNode); }
    if (profile==='ultrawide') { assert.equal(components.evidence.parentNode.id,'inspection-dock'); assert.equal(components.inspection.parentNode,components.project.parentNode); }
  }
  const menu=get('#menu-dialog');
  context.S.preferenceLayout='tablet'; context.composeLayout(true);
  menu.open=true; menu.append(components.more);
  context.composeLayout(true);
  assert.equal(components.more.parentNode,menu,'An open app menu retains its content after recomposition');
  context.S.preferenceLayout='phone'; context.composeLayout(true);
  assert.equal(menu.open,false,'Phone navigation replaces the app-menu dialog');
  assert.equal(context.S.phoneTab,'more','The same menu remains selected in phone navigation');
  context.restoreMenuContent(); // Native close events arrive after the DOM move.
  assert.equal(components.more.parentNode.dataset.phonePanel,'more','A queued dialog close cannot remove the phone menu');
  checkUnique();
});

test('API requests stay under the mounted application path and keep credentials out of URLs', async () => {
  for (const base of ['https://example.invalid/','https://example.invalid/swarm/']) {
    const requests=[];
    const context=vm.createContext({URL,AbortController,TypeError,Error,S:{token:'fixture-only'},APP_BASE:new URL(base),setTimeout:()=>1,clearTimeout:()=>{},fetch:async (url,init)=>{requests.push({url:String(url),init});return {ok:true,json:async()=>({ok:true})};}});
    vm.runInContext(implementation('api'),context);
    await context.api('/router/apply',{method:'POST',body:{mode:'smart'}});
    assert.equal(requests[0].url,base+'api/router/apply');
    assert.equal(requests[0].init.headers.Authorization,'Bearer fixture-only');
    assert.equal(requests[0].init.body,'{"mode":"smart"}');
    assert.ok(!requests[0].url.includes('fixture-only'));
  }
});

test('an explicitly failed account check cannot be displayed as connected', () => {
  const context=vm.createContext({});vm.runInContext(implementation('accountStatus'),context);
  assert.equal(context.accountStatus({checked:true,status:'error',key_present:true})[0],'Check failed');
  assert.equal(context.accountStatus({checked:true,status:'ready',key_present:true})[0],'Connection checked');
  assert.equal(context.accountStatus({checked:false,status:'unchecked',key_present:true})[0],'Key saved · not checked');
  assert.equal(context.accountStatus({checked:false,status:'missing',key_present:false})[0],'Key needed');
  assert.equal(context.accountStatus({checked:false,status:'disabled',key_present:true})[0],'Role disabled');
});

test('interface references and persistence follow the deployed-page contract', () => {
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(match=>match[1]);
  assert.equal(new Set(ids).size,ids.length,'Every authored ID is unique');
  const dynamic=new Set(['inspection-dock','inspect-project-button','menu-dialog']);
  for (const match of source.matchAll(/\$\('#([a-z][a-z0-9-]*)'\)/g)) assert.ok(ids.includes(match[1])||dynamic.has(match[1]),`DOM target ${match[1]}`);
  for (const match of html.matchAll(/<(?:link|script)\b[^>]*(?:src|href)="([^"]+)"/g)) assert.ok(!match[1].startsWith('/'),'Assets remain relative to the app mount');
  const keys=[...source.matchAll(/(?:readPreference|savePreference)\('([^']+)'/g)].map(match=>match[1]);
  assert.deepEqual([...new Set(keys)].sort(),['swarm.layout','swarm.theme']);
  assert.ok(!/innerHTML\s*=/.test(source),'Untrusted server text is not treated as HTML');
  assert.match(html,/href="help\/quickstart\.html"/);assert.match(html,/href="help\/manual\.html"/);
});


test('an edited role timeout takes effect without closing model settings', () => {
  const context=vm.createContext({S:{providers:{lead:{timeout_seconds:120}}}});
  vm.runInContext(implementation('providerCheckTimeout'),context);
  assert.equal(context.providerCheckTimeout('lead'),130000);
  context.S.providers.lead.timeout_seconds=600;
  assert.equal(context.providerCheckTimeout('lead'),610000);
});

test('task readiness follows the selected team rather than a different configured team', () => {
  class Node {
    constructor(text=''){this.textContent=text;this.children=[];this.dataset={};}
    append(...items){this.children.push(...items);} replaceChildren(){this.children=[];}
    addEventListener(){}
  }
  const result=new Node(),select={value:'smart'};
  const context=vm.createContext({S:{connected:true,setup:{ready:true,verified:true},health:{},taskRouter:{mode:'smart',ready:false,missing_roles:['lead'],failed_roles:[],assignments:[]},router:{mode:'manual',ready:true,assignments:[{check:{ok:true}}]}},$:selector=>selector==='#task-readiness'?result:select,icon:()=>new Node(),el:(tag,classes,text)=>new Node(text),roleTitle:role=>role==='lead'?'Builder':role});
  vm.runInContext(implementation('renderTaskReadiness'),context);context.renderTaskReadiness();
  assert.equal(result.dataset.ready,'false');
  assert.match(result.children.map(child=>child.textContent).join(' '),/Builder/);
  assert.doesNotMatch(result.children.map(child=>child.textContent).join(' '),/have been checked/);
  context.S.taskRouter={mode:'smart',ready:true,missing_roles:[],failed_roles:[],assignments:[{check:{ok:true}}]};context.renderTaskReadiness();
  assert.equal(result.dataset.ready,'true');
  assert.match(result.children.map(child=>child.textContent).join(' '),/this selected team have been checked/);
});

test('guided setup only reaches Ready when the newly selected team is ready', async () => {
  for (const result of [
    {ready:false,missing_roles:['lead'],failed_roles:[],expected:/Add account keys for Builder/},
    {ready:false,missing_roles:[],failed_roles:['auditor'],expected:/connection check failed for Auditor/},
    {ready:true,missing_roles:[],failed_roles:[]}
  ]) {
    const errors={textContent:''}, steps=[], requests=[], state={setupStep:3,setup:{ready:true},providers:{}};
    const context=vm.createContext({S:state,Error,$:selector=>selector==='#onboarding-error'?errors:{value:'smart'},applySettingsLocks:()=>{},formError:(node,message)=>{node.textContent=message;},roleTitle:role=>({lead:'Builder',auditor:'Auditor'}[role]||role),applyRouter:async()=>{state.router=result;state.setup=result;return true;},setSetupStep:step=>{state.setupStep=step;steps.push(step);},renderAccounts:()=>{},api:async path=>{requests.push(path);throw new Error('No task or completion request belongs in the Routing step');}});
    vm.runInContext(implementation('setupReadinessIssue')+'\n'+implementation('nextSetupStep'),context);
    await context.nextSetupStep();
    assert.equal(state.setupStep,result.ready?4:2);
    assert.deepEqual(requests,[],'No model request or completion call is implied by choosing a team');
    assert.equal(state.advancingSetup,false);
    if (!result.ready) { assert.match(errors.textContent,result.expected); assert.ok(!steps.includes(4),'No premature Ready screen'); }
  }
});

test('a second Continue cannot skip a guided step while routing is being saved', async () => {
  let finishSave, saves=0;
  const pending=new Promise(resolve=>{finishSave=resolve;});
  const state={setupStep:3,setup:{ready:true},router:{ready:true},providers:{}};
  const context=vm.createContext({S:state,Error,$:()=>({value:'smart'}),applySettingsLocks:()=>{},formError:()=>{},applyRouter:async()=>{saves++;await pending;return true;},setSetupStep:step=>{state.setupStep=step;}});
  vm.runInContext(implementation('nextSetupStep'),context);
  const first=context.nextSetupStep();
  await context.nextSetupStep();
  assert.equal(saves,1);
  assert.equal(state.setupStep,3);
  finishSave(); await first;
  assert.equal(state.setupStep,4);
  assert.equal(state.advancingSetup,false);
});
