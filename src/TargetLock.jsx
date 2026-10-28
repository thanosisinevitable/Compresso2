import { useState } from 'react';
import { ArrowDownToLine, Crosshair, Eye, Image, Plus } from 'lucide-react';
import { api, bytes, Dropzone, errorText, Notice, Progress, useJob } from './ui';
import ArtifactLens from './ArtifactLens';

export default function TargetLock({ available }) {
  const operation=useJob('target'), {job,busy,error,setError}=operation;
  const [files,setFiles]=useState([]),[budget,setBudget]=useState('500'),[resize,setResize]=useState(false);
  const [saved,setSaved]=useState(''),[saving,setSaving]=useState(false),[lens,setLens]=useState(null);
  const result=job?.state==='done'?job.result:null;
  const target=Number(budget)*1024;
  const valid=Number.isInteger(target)&&target>=1024&&target<=100*1024**2;
  const disabled=busy||saving||!available;
  function accept(records){
    if(!records.length)return;
    if(records.length>100||records.some(f=>f.directory||! /\.(png|jpe?g|tiff?|webp|bmp)$/i.test(f.name)))throw new Error('Choose up to 100 single-frame PNG, JPG, TIFF, WebP or BMP images.');
    setFiles(records);setSaved('');operation.reset();
  }
  async function choose(){try{accept(await api.choose('target'));}catch(e){setError(errorText(e));}}
  async function save(){setSaving(true);try{const path=await api.save(job.id);if(path)setSaved(path);}catch(e){setError(errorText(e));}finally{setSaving(false);}}
  return <div className="target-tool">
    <div className="tool-intro"><span className="tool-emblem"><Crosshair size={26}/></span><div><h2>A size limit. A precise landing.</h2><p>Set your budget. Find a JPEG that fits, with quality chosen automatically.</p></div><span className="tag accent">Measured, not estimated</span></div>
    <Notice onClose={()=>setError('')}>{error}</Notice>
    <Dropzone className="panel target-drop" onFiles={accept} onError={setError} disabled={disabled}><Image size={31} strokeWidth={1.3}/><div className="grow"><strong>{files.length?`${files.length} image${files.length===1?'':'s'} selected`:'Drop images to lock their size.'}</strong><small>{files.length?files.slice(0,3).map(f=>f.name).join(', '):'PNG · JPG · TIFF · WebP · BMP · single-frame only'}</small></div><button className="button secondary" disabled={disabled} onClick={choose}><Plus size={15}/>{files.length?'Change images':'Choose images'}</button></Dropzone>
    <div className="panel target-settings"><label className="budget-field">MAXIMUM PER IMAGE<div><input type="number" min="1" max="102400" step="1" value={budget} onChange={e=>setBudget(e.target.value)} aria-label="Target size in KiB" disabled={disabled}/><span>KiB</span></div></label><div className="grow"><label className="checkbox-label"><input type="checkbox" checked={resize} onChange={e=>setResize(e.target.checked)} disabled={disabled}/>Allow resizing if quality alone cannot meet the limit</label><small>Dimensions stay unchanged unless you enable this. JPEG output flattens transparency onto white.</small></div><button className="button primary" disabled={disabled||!files.length||!valid} onClick={()=>{setSaved('');operation.start(files.map(f=>f.path),{targetBytes:target,allowResize:resize});}}><Crosshair size={16}/>Lock target</button></div>
    {!valid&&<Notice>Enter a target between 1 and 102,400 KiB.</Notice>}
    {busy&&<Progress job={job} cancel={operation.cancel}/>}
    {job?.state==='cancelled'&&<Notice tone="info">Target search cancelled. Your originals are untouched.</Notice>}
    {result&&<>
      <div className="target-summary"><strong>{result.successCount} / {result.rows.length} images within budget</strong><span>{bytes(result.outputBytes)} output{result.successCount>1?' including ZIP container':''}</span>{result.successCount>0&&<button className="button primary" disabled={saving} onClick={save}><ArrowDownToLine size={15}/>{saving?'Saving…':'Save target outputs…'}</button>}</div>
      {result.failedCount>0&&<Notice tone="info">{result.failedCount} image(s) could not fit under these constraints. They are excluded from the saved output. Increase the budget or enable resizing and retry.</Notice>}
      <div className="panel target-results">{result.rows.map((row,i)=><article key={i} className="target-row"><div className="grow"><strong>{row.name}</strong><small>{row.met?(row.quality===null?'Original JPEG already fits':`JPEG quality ${row.quality}`):'Target infeasible under these constraints'} · {row.width}×{row.height}{row.resized?' · resized':''}</small><details><summary>{row.attempts.length} encoding attempts</summary><div className="attempts-list">{row.attempts.map((attempt,n)=><span key={n} className={attempt.bytes<=row.targetBytes?'fits':''}>Q{attempt.quality} · {attempt.width}×{attempt.height} · {bytes(attempt.bytes)}</span>)}</div></details></div><div className="target-size"><strong className={row.met?'mint':'muted'}>{row.met?bytes(row.outputBytes):'No output'}</strong><small>limit {bytes(row.targetBytes)}</small></div>{row.met&&<button className="button secondary" onClick={()=>setLens({id:job.id,index:row.lensIndex})} aria-label={`Inspect ${row.name}`}><Eye size={15}/>Inspect</button>}</article>)}</div>
      {saved&&<Notice tone="success">Saved: {saved}<button className="text-button" onClick={()=>api.reveal(saved).catch(e=>setError(errorText(e)))}>Show in Finder</button></Notice>}
    </>}
    <p className="fine-print tool-footnote">The search tests JPEG qualities 1–95 and verifies the bytes of each selected output. It returns the highest quality found within its search, not a guarantee of a global visual optimum. Existing JPEGs already under budget are preserved. Metadata is omitted on new encodings except the sRGB profile.</p>
    {lens&&<ArtifactLens parentId={lens.id} index={lens.index} onClose={()=>setLens(null)}/>}
  </div>;
}
