import { useState } from 'react';
import { Archive, ArrowDownToLine, ChevronUp, Check, FolderOpen, Plus, X } from 'lucide-react';
import { api, bytes, Dropzone, errorText, Notice, Progress, useJob } from './ui';

export default function VersionVault({available}){
  const pack=useJob('vault-create'),open=useJob('vault-open'),restore=useJob('vault-restore');
  const [files,setFiles]=useState([]),[mode,setMode]=useState('create'),[vault,setVault]=useState(null);
  const [saved,setSaved]=useState(''),[error,setError]=useState(''),[saving,setSaving]=useState(false);
  const busy=pack.busy||open.busy||restore.busy;
  const disabled=busy||saving||!available;
  const packed=pack.job?.state==='done'?pack.job.result:null;
  const inspected=open.job?.state==='done'?open.job.result:null;
  const restored=restore.job?.state==='done'?restore.job.result:null;
  const result=mode==='create'?packed:inspected;
  const active=pack.busy?pack:open.busy?open:restore;
  const message=error||pack.error||open.error||restore.error;
  function clearErrors(){setError('');pack.setError('');open.setError('');restore.setError('');}
  function accept(records){
    if(!records.length)return;
    clearErrors();setSaved('');
    if(mode==='open'){
      if(records.length!==1||records[0].directory||! /\.cvault$/i.test(records[0].name))throw new Error('Choose one .cvault archive to open.');
      setVault(records[0]);restore.reset();open.start([records[0].path]);
    }else{
      if(records.length>200||records.some(f=>f.directory))throw new Error('Choose 2–200 regular files, not folders.');
      setFiles(records);pack.reset();
    }
  }
  async function choose(){try{accept(await api.choose(mode==='create'?'vault-create':'vault-open'));}catch(e){setError(errorText(e));}}
  async function save(operation){setSaving(true);try{const path=await api.save(operation.job.id);if(path)setSaved(path);}catch(e){setError(errorText(e));}finally{setSaving(false);}}
  function restoreVersion(version){clearErrors();setSaved('');restore.start([vault.path],{version,identity:inspected.identity});}
  return <div className="vault-tool">
    <div className="tool-intro"><span className="tool-emblem"><Archive size={26}/></span><div><h2>Keep the history. Lose the repetition.</h2><p>A lossless archive that shares unchanged regions between file versions.</p></div><span className="tag">SHA-256 verified restore</span></div>
    <Notice onClose={clearErrors}>{message}</Notice>
    <div className="vault-mode segmented"><button className={mode==='create'?'selected':''} onClick={()=>{setMode('create');clearErrors();setSaved('');}} disabled={disabled}>Create a vault</button><button className={mode==='open'?'selected':''} onClick={()=>{setMode('open');clearErrors();setSaved('');}} disabled={disabled}>Open & restore</button></div>
    <Dropzone className="panel target-drop" onFiles={accept} onError={setError} disabled={disabled}><Archive size={30} strokeWidth={1.3}/><div className="grow"><strong>{mode==='create'?(files.length?`${files.length} versions ready`:'Drop related versions of any file type.'):(vault?.name||'Open a .cvault archive')}</strong><small>{mode==='create'?'First file starts the timeline. Original bytes are preserved.':'Restore one version or export every version as a ZIP.'}</small></div><button className="button secondary" disabled={disabled} onClick={choose}>{mode==='create'?<Plus size={15}/>:<FolderOpen size={15}/ >}{mode==='create'?'Choose versions':'Choose vault'}</button></Dropzone>
    {mode==='create'&&files.length>0&&!packed&&<div className="panel version-inputs">{files.map((file,i)=><div className="version-input" key={file.path}><span className="version-number">{String(i+1).padStart(2,'0')}</span><div className="grow"><strong>{file.name}</strong><small title={file.path}>{file.path}</small></div><span className="muted">{bytes(file.size)}</span><button className="icon-button" aria-label={`Move ${file.name} earlier`} disabled={disabled||i===0} onClick={()=>setFiles(old=>{const next=[...old];[next[i-1],next[i]]=[next[i],next[i-1]];return next;})}><ChevronUp size={17}/></button><button className="icon-button" aria-label={`Remove ${file.name}`} disabled={disabled} onClick={()=>setFiles(old=>old.filter(f=>f.path!==file.path))}><X size={16}/></button></div>)}<div className="vault-action"><small>{files.length<2?'Add at least two file versions.':'Shared chunks are stored once. Incompressible revisions fall back to full-file storage.'}</small><button className="button primary" disabled={disabled||files.length<2} onClick={()=>{clearErrors();setSaved('');pack.start(files.map(f=>f.path));}}><Archive size={16}/>Build vault</button></div></div>}
    {busy&&<Progress job={active.job} cancel={active.cancel}/>}
    {[pack,open,restore].some(op=>op.job?.state==='cancelled')&&!busy&&<Notice tone="info">Operation cancelled. Your source files are unchanged.</Notice>}
    {result&&<>
      <div className="vault-stats stats-grid"><div className="panel stat"><small>ORIGINAL VERSIONS</small><strong>{bytes(result.inputBytes)}</strong></div><div className="panel stat"><small>VAULT SIZE</small><strong className="mint">{bytes(result.outputBytes)}</strong></div><div className="panel stat"><small>{result.outputBytes<=result.inputBytes?'LESS STORAGE':'ARCHIVE OVERHEAD'}</small><strong>{result.inputBytes?`${Math.abs(1-result.outputBytes/result.inputBytes)*100<.1?'0.0':(Math.abs(1-result.outputBytes/result.inputBytes)*100).toFixed(1)}%`:'—'}</strong></div></div>
      <div className="between vault-timeline-heading"><h3>{result.versions.length} versions · one self-contained archive</h3>{mode==='create'?<button className="button primary" disabled={disabled} onClick={()=>save(pack)}><ArrowDownToLine size={15}/>Save vault…</button>:<button className="button primary" disabled={disabled} onClick={()=>restoreVersion('all')}><ArrowDownToLine size={15}/>Restore all versions</button>}</div>
      <div className="panel version-timeline">{result.versions.map((version,i)=><article className="vault-version" key={version.id}><span className="version-number">{String(i+1).padStart(2,'0')}</span><div className="grow"><div className="between"><strong>{version.name}</strong><small>{bytes(version.size)}</small></div><div className="version-track"><i style={{width:version.size?`${Math.max(1,Math.min(100,(version.reusedBytes||0)/version.size*100))}%`:'0%'}}/></div><small>{version.mode==='full'?'Full-file fallback':`${bytes(version.reusedBytes||0)} shared with earlier content`} · {bytes(version.storedBytes||0)} new compressed content</small></div>{mode==='open'&&<button className="button secondary" disabled={disabled} aria-label={`Restore ${version.name}`} onClick={()=>restoreVersion(version.id)}>Restore</button>}</article>)}</div>
      <p className="fine-print">{mode==='create'?'Every version was reconstructed and SHA-256 checked before this vault became available to save.':'Opening reads the index. Each selected version is fully reconstructed and SHA-256 checked before saving.'} Shared bytes and new compressed content exclude ZIP headers and the manifest.</p>
    </>}
    {restored&&mode==='open'&&<div className="panel restored-output"><Check size={22}/><div className="grow"><strong>{restored.outputCount} version(s) restored and verified</strong><small>{bytes(restored.outputBytes)} · {restored.name}</small></div><button className="button primary" disabled={disabled} onClick={()=>save(restore)}>Save restored output…</button></div>}
    {saved&&<Notice tone="success">Saved: {saved}<button className="text-button" onClick={()=>api.reveal(saved).catch(e=>setError(errorText(e)))}>Show in Finder</button></Notice>}
    <p className="fine-print tool-footnote">Content-defined chunk deltas preserve arbitrary file bytes, not just pixels. Related files often benefit; heavily re-encoded images may share little data. Vaults can be larger than the originals. Keep the complete .cvault file to retain all versions.</p>
  </div>;
}
