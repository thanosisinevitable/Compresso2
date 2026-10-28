// Real-backend React interaction checks for environments without a graphical browser.
// This verifies behavior, not pixels or native Electron dialogs.
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { JSDOM } from 'jsdom';
import { build } from 'esbuild';
import { Backend } from '../electron/backend.mjs';

const root=process.cwd(), qa=path.join(root,'.qa');await fs.mkdir(qa,{recursive:true});
const fixtures=await fs.mkdtemp(path.join(qa,'dom-fixtures-'));
const python=process.env.COMPRESSO_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const fixtureScript=`from pathlib import Path
from PIL import Image,ImageDraw
from reportlab.pdfgen import canvas
p=Path(${JSON.stringify(fixtures)})
im=Image.new('RGB',(600,400),'#bba382');d=ImageDraw.Draw(im);d.rectangle((10,90,220,360),fill='blue');d.ellipse((180,40,480,320),fill='red')
im.save(p/'photo.png');im.resize((300,200)).save(p/'resized.jpg',quality=90)
(p/'copy.png').write_bytes((p/'photo.png').read_bytes())
(p/'uniform.bin').write_bytes(bytes(range(256))*1024)
(p/'empty.bin').write_bytes(b'')
doc=canvas.Canvas(str(p/'pages.pdf'),pagesize=(120,80));doc.drawString(10,40,'First page');doc.showPage();doc.drawString(10,40,'Second page');doc.showPage();doc.save()
`;
const generated=spawnSync(python,['-c',fixtureScript],{encoding:'utf8'});assert.equal(generated.status,0,generated.stderr);
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost/',pretendToBeVisual:true});
for(const name of ['window','document','HTMLElement','HTMLInputElement','SVGElement','Element','Node','MutationObserver'])globalThis[name]=dom.window[name];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.getComputedStyle=dom.window.getComputedStyle.bind(dom.window);
globalThis.requestAnimationFrame=dom.window.requestAnimationFrame.bind(dom.window);
globalThis.cancelAnimationFrame=dom.window.cancelAnimationFrame.bind(dom.window);
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
window.matchMedia=()=>({matches:true,addEventListener(){},removeEventListener(){},addListener(){},removeListener(){}});
globalThis.ResizeObserver=class { constructor(callback){this.callback=callback;} observe(target){this.callback([{target,contentRect:{width:600,height:230}}]);} unobserve(){} disconnect(){} };
globalThis.IntersectionObserver=class {constructor(callback){this.callback=callback;} observe(target){queueMicrotask(()=>this.callback([{target,isIntersecting:true}]));} disconnect(){} };
window.ResizeObserver=globalThis.ResizeObserver;window.IntersectionObserver=globalThis.IntersectionObserver;
HTMLElement.prototype.getBoundingClientRect=function(){return {width:600,height:230,top:0,left:0,right:600,bottom:230,x:0,y:0,toJSON(){return {};}};};
SVGElement.prototype.getBBox=()=>({x:0,y:0,width:20,height:10});
const backend=new Backend(root,root,false);let view;let entropyFile='uniform.bin',compressionFile='photo.png',trashConfirmed=false,vaultSaved=null;
let previews=0,reveals=0;
const record=async(name,directory=false)=>{const filename=name===null?fixtures:path.join(fixtures,name);const stat=await fs.stat(filename);return {path:filename,name:path.basename(filename),size:stat.size,directory};};
try{
 await backend.start();
 window.compresso={platform:'darwin',health:()=>backend.request('/health'),
  choose:async kind=>{
    if(kind==='scan')return [await record(null,true)];
    if(kind==='vault-create')return [await record('photo.png'),await record('copy.png'),await record('resized.jpg')];
    if(kind==='vault-open'){const stat=await fs.stat(vaultSaved);return [{path:vaultSaved,name:path.basename(vaultSaved),size:stat.size,directory:false}];}
    return [await record(kind==='entropy'?entropyFile:kind==='compress'?compressionFile:'photo.png')];
  },
  drop:async files=>Promise.all(files.map(file=>record(file.name))),
  start:request=>backend.request('/jobs',request),status:id=>backend.request('/jobs/'+id),cancel:id=>backend.request('/jobs/'+id+'/cancel',{}),
  thumbnail:(id,value)=>backend.request(`/jobs/${id}/thumbnail`,{path:value}),
  lens:async(id,index,gain)=>{const parent=await backend.request('/jobs/'+id);const pair=parent.result.lensPairs[index];return backend.request('/jobs',{kind:'lens',paths:[pair.source,pair.output],options:{gain,identity:pair.identity}});},
  asset:(id,key)=>backend.request(`/jobs/${id}/asset`,{key}),
  preview:async()=>{previews++;},reveal:async()=>{reveals++;},
  save:async id=>{const {result,kind}=await backend.request('/jobs/'+id);const out=path.join(qa,'dom-'+result.name);await fs.copyFile(result.artifact,out);if(kind==='vault-create')vaultSaved=out;return out;},
  trash:async(id,paths)=>{await backend.request(`/jobs/${id}/cleanup-check`,{paths});trashConfirmed=true;return {cancelled:true,moved:[],errors:[]};},
 };
 await build({entryPoints:[path.join(root,'src/App.jsx')],outfile:path.join(qa,'app-test.mjs'),bundle:true,packages:'external',platform:'node',format:'esm',jsx:'automatic',external:['react','react-dom','react-dom/*'],loader:{'.css':'empty'},define:{'process.env.NODE_ENV':'"test"'},logLevel:'silent'});
 const React=await import('react');const {render,screen,fireEvent,waitFor,within,cleanup}=await import('@testing-library/react');
 const {default:App}=await import('../.qa/app-test.mjs');view=render(React.createElement(App));
 const wait=fn=>waitFor(fn,{timeout:15000});
 const click=(name)=>fireEvent.click(screen.getByRole('button',{name,exact:true}));
 await wait(()=>assert.ok(screen.getByText('All local. All yours.')));
 click('Choose files');await wait(()=>assert.ok(screen.getByRole('button',{name:'Compress files',exact:true})));
 click('Compress files');await wait(()=>assert.ok(screen.getByRole('button',{name:'Save as…',exact:true})));
 click('Save as…');await wait(()=>assert.ok(screen.getByText(/^Saved:/)));
 click('Show in Finder');await wait(()=>assert.equal(reveals,1));
 console.log('PASS DOM: file choice → real compression → save → reveal');
 click('Ghost Hunt');fireEvent.click(screen.getByRole('button',{name:/Choose a folder/}));await wait(()=>assert.equal(screen.getByRole('button',{name:'Start scan'}).disabled,false));
 click('Start scan');await wait(()=>assert.ok(screen.getByText('Identical contents')));
 assert.equal(document.querySelectorAll('.duplicate-file input:checked').length,0);
 click('Select extra exact copies');assert.equal(document.querySelectorAll('.duplicate-file input:checked').length,1);
 click('Move to Trash…');await wait(()=>assert.equal(trashConfirmed,true));assert.ok((await fs.stat(path.join(fixtures,'copy.png'))).isFile());
 await wait(()=>assert.equal(screen.getByRole('button',{name:'Clear selection'}).disabled,false));click('Clear selection');
 fireEvent.click(screen.getByRole('button',{name:/Similar images/}));await wait(()=>assert.ok(screen.getByText('A familiar image')));
 assert.equal(document.querySelectorAll('.duplicate-file input:checked').length,0);
 fireEvent.click(screen.getAllByRole('button',{name:/Preview /})[0]);assert.equal(previews,1);
 const boxes=[...document.querySelectorAll('.duplicate-file input')];boxes.forEach(box=>fireEvent.click(box));
 click('Move to Trash…');await wait(()=>assert.ok(screen.getByText('Keep at least one file in every group, including overlapping groups.')));
 click('Dismiss message');click('Clear selection');
 console.log('PASS DOM: exact and visual groups, no automatic selection, cancelled Trash, keeper guard, preview');
 click('Entropy Lab');click('Choose a file');await wait(()=>assert.ok(screen.getByText('8.000')));
 assert.equal(document.querySelectorAll('.heatmap button').length,256);
 fireEvent.focus(document.querySelectorAll('.heatmap button')[40]);assert.match(document.querySelector('.heatmap-detail').textContent,/041/);
 assert.equal(document.querySelectorAll('.recharts-bar-rectangle').length,256);
 entropyFile='empty.bin';click('Change file');await wait(()=>assert.ok(screen.getByText('No bytes to analyze')));
 assert.ok(screen.getByText('No chunks: this file is empty.'));
 console.log('PASS DOM: exact entropy, 256 histogram bars, heatmap keyboard interaction, empty-file handling');
 click('Compress');assert.ok(within(document.querySelector('.compress-section')).getByText(/^Saved:/));
 // Wrong-type drops produce a visible error instead of attempting to process a folder as an image.
 fireEvent.drop(document.querySelector('.compress-drop'),{dataTransfer:{files:[{name:'uniform.bin'}]}});
 await wait(()=>assert.match(screen.getByRole('alert').textContent,/Choose PNG.*WebP.*BMP.*PDF/));
 console.log('PASS DOM: section state retention and invalid-drop error handling');
 click('Dismiss message');
 click('Inspect image');
 await wait(()=>assert.ok(screen.getByRole('dialog',{name:'Artifact Lens'})));
 await wait(()=>assert.ok(screen.getByText('STRUCTURAL SIMILARITY')));
 fireEvent.change(screen.getByRole('slider',{name:'Before and after split'}),{target:{value:'30'}});
 assert.equal(screen.getByRole('slider',{name:'Before and after split'}).value,'30');
 click('Heatmap');assert.ok(screen.getByRole('img',{name:/heatmap amplified/}));
 fireEvent.change(screen.getByRole('combobox',{name:'Comparison zoom'}),{target:{value:'2'}});
 assert.equal(screen.getByRole('combobox',{name:'Comparison zoom'}).value,'2');
 click('Close Artifact Lens');
 console.log('PASS DOM: real SSIM and preview assets, comparison split, heatmap, zoom and modal close');
 click('Target Lock');click('Choose images');
 await wait(()=>assert.equal(screen.getByRole('button',{name:'Lock target'}).disabled,false));
 fireEvent.change(screen.getByRole('spinbutton',{name:'Target size in KiB'}),{target:{value:'10'}});
 click('Lock target');await wait(()=>assert.ok(screen.getByText('1 / 1 images within budget')));
 assert.match(document.querySelector('.target-size').textContent,/10 KiB/);
 click('Save target outputs…');await wait(()=>assert.ok(within(document.querySelector('.target-tool')).getByText(/^Saved:/)));
 click('Version Vault');click('Choose versions');
 await wait(()=>assert.equal(screen.getByRole('button',{name:'Build vault'}).disabled,false));
 click('Build vault');await wait(()=>assert.ok(screen.getByRole('button',{name:'Save vault…'})));
 assert.ok(screen.getByText(/Every version was reconstructed/));
 click('Save vault…');await wait(()=>assert.ok(vaultSaved));
 click('Open & restore');click('Choose vault');
 await wait(()=>assert.ok(screen.getByRole('button',{name:'Restore photo.png'})));
 click('Restore photo.png');await wait(()=>assert.ok(screen.getByRole('button',{name:'Save restored output…'})));
 click('Save restored output…');await wait(()=>assert.ok(within(document.querySelector('.vault-tool')).getByText(/^Saved:/)));
 assert.deepEqual(await fs.readFile(path.join(qa,'dom-photo.png')),await fs.readFile(path.join(fixtures,'photo.png')));
 console.log('PASS DOM: target size workflow; vault create/save/open/restore with byte-identical output');

 click('Standard');
 assert.equal(screen.queryByText('TIFF output'),null);
 assert.equal(screen.getByRole('combobox',{name:'Output format'}).options.length,7);
 fireEvent.change(screen.getByRole('combobox',{name:'Output format'}),{target:{value:'jpg'}});
 click('Convert files');await wait(()=>assert.ok(screen.getByRole('button',{name:'Save as…'})));
 click('Save as…');await wait(()=>assert.ok(within(document.querySelector('.compress-section')).getByText(/^Saved:/)));
 const converted=await fs.readFile(path.join(qa,'dom-photo.jpg'));assert.equal(converted[0],0xff);assert.equal(converted[1],0xd8);
 click('Start again');compressionFile='pages.pdf';click('Choose files');
 await wait(()=>assert.ok(screen.getByRole('combobox',{name:'PDF image resolution'})));
 fireEvent.change(screen.getByRole('combobox',{name:'PDF image resolution'}),{target:{value:'72'}});
 click('Convert files');await wait(()=>assert.ok(screen.getByRole('button',{name:'Save as…'})));
 click('Save as…');await wait(()=>assert.ok(within(document.querySelector('.compress-section')).getByText(/^Saved:/)));
 const archiveCheck=spawnSync(python,['-c','import zipfile,sys;z=zipfile.ZipFile(sys.argv[1]);assert z.namelist()==["pages-page-001.jpg","pages-page-002.jpg"]',path.join(qa,'dom-compressed.zip')],{encoding:'utf8'});
 assert.equal(archiveCheck.status,0,archiveCheck.stderr);
 console.log('PASS DOM: generic format selection, real PNG-to-JPEG save, all-page PDF export and resolution choice');

 cleanup();view=null;
}finally{
 if(view)view.unmount();await backend.stop();dom.window.close();
}
