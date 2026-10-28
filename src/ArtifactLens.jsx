import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Eye, X, ZoomIn } from 'lucide-react';
import { api, bytes, errorText, Notice, Progress } from './ui';

export default function ArtifactLens({ parentId, index, onClose }) {
  const [job,setJob] = useState(null), [error,setError] = useState(''), [assets,setAssets] = useState({});
  const [mode,setMode] = useState('compare'), [split,setSplit] = useState(50), [zoom,setZoom] = useState(1);
  const [gain,setGain] = useState(8), [appliedGain,setAppliedGain] = useState(8);
  const dialog = useRef(null), generation = useRef(0), closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.current?.focus();
    function key(event) {
      if (event.key === 'Escape') {event.preventDefault();closeRef.current();}
      if (event.key === 'Tab') {
        const nodes = [...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled),[tabindex="0"]')];
        if (!nodes.length) return;
        if (event.shiftKey && document.activeElement === nodes[0]) {event.preventDefault();nodes.at(-1).focus();}
        else if (!event.shiftKey && document.activeElement === nodes.at(-1)) {event.preventDefault();nodes[0].focus();}
      }
    }
    document.addEventListener('keydown',key);
    return () => {document.body.style.overflow=overflow;document.removeEventListener('keydown',key);previous?.focus();};
  },[]);
  useEffect(() => {
    let stopped=false, timer, identity;
    const current=++generation.current;
    setError('');setJob(null);setAssets({});
    async function poll() {
      try {
        const update=await api.status(identity);
        if(stopped || current!==generation.current)return;
        setJob(update);
        if(update.state==='done') {
          const keys=['original','compressed','difference','heatmap'];
          const images=await Promise.all(keys.map(key=>api.asset(identity,key)));
          if(!stopped)setAssets(Object.fromEntries(keys.map((key,i)=>[key,images[i].data])));
        } else if(update.state==='error')setError(update.error);
        else if(['queued','running'].includes(update.state))timer=setTimeout(poll,350);
      }catch(e){if(!stopped)setError(errorText(e));}
    }
    api.lens(parentId,index,appliedGain).then(result=>{
      identity=result.id;
      if(stopped){api.cancel(identity).catch(()=>{});return;}
      poll();
    }).catch(e=>{if(!stopped)setError(errorText(e));});
    return ()=>{stopped=true;clearTimeout(timer);if(identity)api.cancel(identity).catch(()=>{});};
  },[parentId,index,appliedGain]);
  const result=job?.state==='done'?job.result:null;
  const busy=!error && (!result || !assets.original);
  return createPortal(<div className="lens-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose();}}>
    <div className="lens-dialog panel" role="dialog" aria-modal="true" aria-label="Artifact Lens" ref={dialog} tabIndex={-1}>
      <div className="lens-header"><span className="group-symbol similar"><Eye size={20}/></span><div className="grow"><div className="eyebrow">ARTIFACT LENS</div><h2>{result?.name || 'Look closer.'}</h2></div><button className="icon-button" aria-label="Close Artifact Lens" onClick={onClose}><X size={20}/></button></div>
      <Notice>{error}</Notice>
      {error && <p className="fine-print">If the engine restarted, run the compression or conversion again, then reopen Inspect.</p>}
      {busy && <Progress job={job} cancel={onClose}/>}
      {result && assets.original && <>
        <div className="lens-toolbar"><div className="segmented">{[['compare','Before / after'],['difference','Difference'],['heatmap','Heatmap']].map(([value,label])=><button key={value} className={mode===value?'selected':''} aria-pressed={mode===value} onClick={()=>setMode(value)}>{label}</button>)}</div><label className="lens-zoom"><ZoomIn size={15}/><select aria-label="Comparison zoom" value={zoom} onChange={e=>setZoom(Number(e.target.value))}>{[1,2,4].map(n=><option key={n} value={n}>{n}×</option>)}</select></label></div>
        <div className="lens-scroll" tabIndex={0} aria-label="Scrollable image comparison">
          <div className="lens-canvas" style={{width:`${zoom*100}%`,aspectRatio:`${result.previewWidth} / ${result.previewHeight}`}}>
            <img src={mode==='compare'?assets.compressed:assets[mode]} alt={mode==='compare'?'Compressed image':`${mode} amplified ${result.gain} times`}/>
            {mode==='compare' && <img className="lens-original" src={assets.original} style={{clipPath:`inset(0 ${100-split}% 0 0)`}} alt="Original image"/>}
            {mode==='compare' && <div className="lens-divider" style={{left:`${split}%`}}><span>↔</span></div>}
            <span className="lens-image-label">{mode==='compare'?'ORIGINAL':mode.toUpperCase()}</span>{mode==='compare' && <span className="lens-image-label right">OUTPUT</span>}
          </div>
        </div>
        {mode==='compare'?<label className="split-control">Original<input aria-label="Before and after split" type="range" min="0" max="100" value={split} onChange={e=>setSplit(Number(e.target.value))}/>Output</label>:<div className="gain-control"><label>Amplification<select aria-label="Difference amplification" value={gain} onChange={e=>setGain(Number(e.target.value))}>{[1,4,8,16,32].map(n=><option key={n} value={n}>{n}×</option>)}</select></label><button className="text-button" disabled={gain===appliedGain} onClick={()=>setAppliedGain(gain)}>Apply amplification</button><small>Brighter areas contain larger pixel differences.</small></div>}
        <div className="lens-metrics"><div><small>STRUCTURAL SIMILARITY</small><strong>{result.ssim===null?'N/A':result.ssim.toFixed(4)}</strong></div><div><small>MEAN BYTE DIFFERENCE</small><strong>{result.meanAbsoluteError.toFixed(2)}<em> / 255</em></strong></div><div><small>FILE SIZE</small><strong>{bytes(result.inputBytes)} <em>→</em> {bytes(result.outputBytes)}</strong></div></div>
        <p className="fine-print">Comparison uses orientation-corrected sRGB images at {result.previewWidth}×{result.previewHeight}, up to {result.previewEdge} px per edge. Zoom enlarges this preview. SSIM is a structural metric, not a percentage of quality retained.</p>
        {result.resized && <Notice tone="info">Output dimensions changed: {result.originalWidth}×{result.originalHeight} → {result.outputWidth}×{result.outputHeight}. The reference is resized to match for this comparison, so the score does not measure the loss of original resolution.</Notice>}
        {result.identicalPreview && <p className="fine-print mint">The compared preview pixels are identical. Files may still differ in metadata or full-resolution content.</p>}
      </>}
    </div>
  </div>,document.body);
}
