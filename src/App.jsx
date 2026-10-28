import { useEffect, useState } from 'react';
import { MotionConfig, motion } from 'framer-motion';
import { ArrowDownToLine, Binary, Ghost, RotateCw } from 'lucide-react';
import Compress from './CompressHub';
import GhostHunt from './GhostHunt';
import EntropyLab from './EntropyLab';
import { api, errorText, Notice } from './ui';
import './App.css';

const tabs = [{id:'compress',label:'Compress',icon:ArrowDownToLine},{id:'ghost',label:'Ghost Hunt',icon:Ghost},{id:'entropy',label:'Entropy Lab',icon:Binary}];
export default function App() {
  const [tab,setTab] = useState('compress'), [health,setHealth] = useState(null), [engineError,setEngineError] = useState('');
  useEffect(() => {
    if (!api) { setEngineError('Open the desktop app with npm run dev or npm start to use local files.'); return; }
    let stopped = false, timer;
    async function check() {
      try { const result = await api.health(); if (!stopped) { setHealth(result); setEngineError(''); } }
      catch(e) { if (!stopped) { setHealth(null); setEngineError(errorText(e)); } }
      if (!stopped) timer = setTimeout(check, 5000);
    }
    check(); return () => { stopped = true; clearTimeout(timer); };
  }, []);
  useEffect(() => {
    const prevent = event => event.preventDefault();
    window.addEventListener('dragover',prevent);window.addEventListener('drop',prevent);
    return () => {window.removeEventListener('dragover',prevent);window.removeEventListener('drop',prevent);};
  }, []);
  return <MotionConfig reducedMotion="user"><div className={`app-shell platform-${api?.platform || 'preview'}`}>
    <header className="titlebar"><div className="wordmark"><span className="brand-mark"><i/><i/><i/></span>compresso<span className="version">2.2</span></div><span className="titlebar-caption">A LITTLE LESS. A LOT MORE.</span></header>
    <div className="navigation-row"><nav aria-label="Main sections">{tabs.map(({id,label,icon:Icon})=><button key={id} className={tab===id ? 'active' : ''} aria-current={tab===id ? 'page' : undefined} onClick={()=>setTab(id)}>{tab===id && <motion.span className="nav-highlight" layoutId="nav" transition={{duration:.2}}/>}<Icon size={16}/><span>{label}</span></button>)}</nav><span className="engine-status"><span className={`status-dot ${health ? '' : 'waiting'}`}/>{health ? 'All local. All yours.' : engineError ? 'Engine unavailable' : 'Starting engine…'}</span></div>
    {engineError && <div className="engine-notice"><Notice>{engineError}</Notice>{api && <button className="button secondary" onClick={()=>{setEngineError('Restarting…');api.restart().catch(e=>setEngineError(errorText(e)));}}><RotateCw size={14}/>Restart engine</button>}</div>}
    {health && !health.ghostscript && <div className="engine-notice"><Notice tone="info">PDF compression and multipage TIFF-to-PDF merging need Ghostscript. Install it with brew install ghostscript and restart the app. Other tools are ready.</Notice></div>}
    <main><div hidden={tab!=='compress'}><Compress available={!!health}/></div><div hidden={tab!=='ghost'}><GhostHunt available={!!health}/></div><div hidden={tab!=='entropy'}><EntropyLab available={!!health}/></div></main>
    <footer><span className="footer-mark">C</span><span>Less storage. More possibility.</span><span>PRIVATE BY DESIGN · PROCESSED ON YOUR DEVICE</span></footer>
  </div></MotionConfig>;
}
