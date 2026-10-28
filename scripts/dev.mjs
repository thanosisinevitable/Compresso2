import { spawn } from 'node:child_process';
import path from 'node:path';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const children=[];
let exiting=false;
function stop(code=0) {if(exiting)return;exiting=true;for(const child of children) child.kill('SIGTERM');process.exitCode=code;}
const vite=spawn(process.execPath,[path.resolve('node_modules/vite/bin/vite.js')],{stdio:'inherit'});
children.push(vite);vite.on('exit',code=>stop(code??1));vite.on('error',error=>{console.error(error);stop(1);});
let ready=false;
for(let i=0;i<100 && !exiting;i++){
 try{const response=await fetch('http://127.0.0.1:5173');if(response.ok){ready=true;break;}}catch{/* Wait for Vite. */}
 await new Promise(resolve=>setTimeout(resolve,100));
}
if(!ready)stop(1);
else if(!exiting){
 const env={...process.env,COMPRESSO_DEV_URL:'http://127.0.0.1:5173/'};delete env.ELECTRON_RUN_AS_NODE;
 const electron=spawn(require('electron'),['.'],{stdio:'inherit',env});children.push(electron);
 electron.on('exit',code=>stop(code??0));electron.on('error',error=>{console.error(error);stop(1);});
}
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
