// Browser integration test: the real Python engine, with native dialogs represented by deterministic fixtures.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { Backend } from '../electron/backend.mjs';

const root=process.cwd(), qa=path.join(root,'.qa');
await fs.mkdir(qa,{recursive:true});
const fixtures=path.join(qa,'fixtures');await fs.mkdir(fixtures,{recursive:true});
const python=process.env.COMPRESSO_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const generated=spawnSync(python,['-c',`
from pathlib import Path
from PIL import Image, ImageDraw
p=Path(${JSON.stringify(fixtures)})
im=Image.new('RGB',(640,480),'#a7978f');d=ImageDraw.Draw(im)
d.rectangle((20,200,360,470),fill='#4a5953');d.ellipse((180,60,520,400),fill='#c8ab79');d.line((0,0,639,479),fill='white',width=12)
im.save(p/'Studio-original.png');im.resize((320,240)).save(p/'Studio-resized.jpg',quality=95)
(p/'Studio-copy.png').write_bytes((p/'Studio-original.png').read_bytes())
(p/'Uniform-bytes.bin').write_bytes(bytes(range(256))*1024)
(p/'Empty.bin').write_bytes(b'')
`],{encoding:'utf8'});
if(generated.status!==0)throw new Error(generated.stderr);
const backend=new Backend(root,root,false);let browser,server;
let chosenEntropy='Uniform-bytes.bin';let revealed=0,previewed=0;
const record=async(name,directory=false)=>{const filename=name===null?fixtures:path.join(fixtures,name);const stat=await fs.stat(filename);return {path:filename,name:path.basename(filename),size:stat.size,directory};};
try{
 await backend.start();
 server=createServer(async(req,res)=>{
  try{
   const pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);
   const target=path.resolve(root,'dist',pathname==='/'?'index.html':'.'+pathname);
   if(!target.startsWith(path.join(root,'dist')+path.sep)){res.writeHead(403).end();return;}
   const data=await fs.readFile(target);
   res.setHeader('Content-Type',({'.js':'text/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'})[path.extname(target)]||'application/octet-stream');res.end(data);
  }catch{res.writeHead(404).end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 browser=await chromium.launch({headless:true,...(process.env.COMPRESSO_TEST_CHROMIUM?{executablePath:process.env.COMPRESSO_TEST_CHROMIUM,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']}: {})});
 const page=await browser.newPage({viewport:{width:1200,height:900},reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.exposeFunction('desktopCall',async(method,args=[])=>{
  switch(method){
   case 'health':return backend.request('/health');
   case 'choose':return args[0]==='scan'?[await record(null,true)]:[await record(args[0]==='entropy'?chosenEntropy:'Studio-original.png')];
   case 'drop':return Promise.all(args[0].map(name=>record(name)));
   case 'start':return backend.request('/jobs',args[0]);
   case 'status':return backend.request('/jobs/'+args[0]);
   case 'cancel':return backend.request('/jobs/'+args[0]+'/cancel',{});
   case 'thumbnail':return backend.request('/jobs/'+args[0]+'/thumbnail',{path:args[1]});
   case 'preview':previewed++;return true;
   case 'reveal':revealed++;return true;
   case 'save':{const job=await backend.request('/jobs/'+args[0]);const output=path.join(qa,'saved-'+job.result.name);await fs.copyFile(job.result.artifact,output);return output;}
   case 'trash':await backend.request('/jobs/'+args[0]+'/cleanup-check',{paths:args[1]});return {cancelled:true,moved:[],errors:[]};
   default:throw new Error('Unexpected bridge method: '+method);
  }
 });
 await page.addInitScript(()=>{
  const names=['health','choose','start','status','cancel','thumbnail','preview','reveal','save','trash','restart'];
  window.compresso=Object.fromEntries(names.map(name=>[name,(...args)=>window.desktopCall(name,args)]));
  window.compresso.platform='darwin';
  window.compresso.drop=files=>window.desktopCall('drop',[Array.from(files,f=>f.name)]);
 });
 await page.goto(`http://127.0.0.1:${server.address().port}/`);
 await page.getByText('All local. All yours.').waitFor();
 await page.screenshot({path:path.join(qa,'compress.png'),fullPage:true});
 await page.getByRole('button',{name:'Choose files',exact:true}).click();
 await page.getByRole('button',{name:'Compress files',exact:true}).click();
 await page.getByRole('button',{name:'Save as…',exact:true}).waitFor();
 await page.getByRole('button',{name:'Save as…',exact:true}).click();
 await page.getByText('Saved:',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Show in Finder'}).click();assert.equal(revealed,1);
 console.log('PASS: choose → real compression → save and reveal bridge');
 await page.getByRole('button',{name:'Ghost Hunt',exact:true}).click();
 await page.getByRole('button',{name:'Choose a folder',exact:false}).click();
 await page.getByRole('button',{name:'Start scan',exact:true}).click();
 await page.getByText('Identical contents',{exact:true}).waitFor();
 assert.equal(await page.locator('.duplicate-file input:checked').count(),0);
 await page.getByRole('button',{name:'Select extra exact copies'}).click();
 assert.equal(await page.locator('.duplicate-file input:checked').count(),1);
 await page.getByRole('button',{name:'Move to Trash…'}).click();
 await page.getByRole('button',{name:'Move to Trash…'}).waitFor();
 assert.equal((await fs.stat(path.join(fixtures,'Studio-copy.png'))).isFile(),true);
 await page.getByRole('button',{name:'Clear selection'}).click();
 await page.getByRole('button',{name:/Similar images/}).click();
 await page.getByText('A familiar image',{exact:true}).waitFor();
 assert.equal(await page.locator('.duplicate-file input:checked').count(),0);
 await page.locator('.duplicate-file').first().getByRole('button',{name:/Preview/}).click();assert.equal(previewed,1);
 await page.locator('.duplicate-file input').first().check();await page.locator('.duplicate-file input').nth(1).check();
 await page.getByRole('button',{name:'Move to Trash…'}).click();
 await page.getByText('Keep at least one file in every group, including overlapping groups.').waitFor();
 await page.getByRole('button',{name:'Dismiss message'}).click();await page.getByRole('button',{name:'Clear selection'}).click();
 await page.screenshot({path:path.join(qa,'ghost-hunt.png'),fullPage:true});
 console.log('PASS: real exact/pHash results, manual selections, overlap keeper guard, preview, cancelled cleanup');
 await page.getByRole('button',{name:'Entropy Lab',exact:true}).click();
 await page.getByRole('button',{name:'Choose a file',exact:true}).click();
 await page.getByText('8.000',{exact:true}).waitFor();
 assert.equal(await page.locator('.heatmap button').count(),256);
 await page.locator('.heatmap button').nth(40).hover();
 assert.match(await page.locator('.heatmap-detail').innerText(),/041/);
 await page.screenshot({path:path.join(qa,'entropy-lab.png'),fullPage:true});
 await page.setViewportSize({width:860,height:700});
 await page.screenshot({path:path.join(qa,'entropy-small.png'),fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Horizontal overflow at minimum window width');
 chosenEntropy='Empty.bin';await page.getByRole('button',{name:'Change file',exact:true}).click();
 await page.getByText('No bytes to analyze',{exact:true}).waitFor();
 await page.getByText('No chunks: this file is empty.',{exact:true}).waitFor();
 console.log('PASS: known entropy, all 256 heatmap sections, empty file, minimum-window layout');
 await page.getByRole('button',{name:'Compress',exact:true}).click();
 await page.getByText('Saved:',{exact:false}).waitFor();
 assert.deepEqual(errors,[]);
 console.log('PASS: section state retention; no browser exceptions');
}finally{
 if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));await backend.stop();
}
