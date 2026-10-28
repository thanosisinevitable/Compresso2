import { useMemo, useState } from 'react';
import { Check, ChevronLeft, ChevronRight, Eye, Folder, FolderOpen, Ghost, ScanLine, Trash2 } from 'lucide-react';
import { api, bytes, Dropzone, errorText, FileThumbnail, Notice, Progress, SectionHeading, useJob } from './ui';

function Group({ group, jobId, selected, toggle, onError, disabled }) {
  const [limit, setLimit] = useState(12);
  return <article className="panel duplicate-group"><div className="group-heading"><span className={`group-symbol ${group.kind}`}><Ghost size={19}/></span><div className="grow"><h3>{group.kind === 'exact' ? 'Identical contents' : 'A familiar image'}</h3><small>{group.files.length} files · {group.kind === 'exact' ? 'SHA-256 verified' : 'pHash candidates · review required'}</small></div><div className="group-space"><strong>{bytes(group.potentialBytes)}</strong><small>{group.kind === 'exact' ? 'extra copy size' : 'excluding reference'}</small></div></div>
    {group.files.slice(0,limit).map((file,index) => <div className={`duplicate-file ${selected.has(file.path) ? 'checked' : ''}`} key={file.path}>
      <input type="checkbox" aria-label={`Select ${file.path}`} checked={selected.has(file.path)} onChange={() => toggle(file.path)} disabled={disabled}/>
      <FileThumbnail file={file} jobId={jobId}/><div className="file-info"><div className="row"><strong title={file.name}>{file.name}</strong>{index === 0 && <span className="tiny-tag">{group.kind === 'exact' ? 'Suggested keep' : 'Reference'}</span>}</div><small title={file.path}>{file.path}</small></div>
      <div className="file-metrics"><span>{bytes(file.size)}</span>{group.kind === 'similar' && <small title={`${file.distance} of 64 hash bits differ from the reference`}>{file.similarity.toFixed(1)}% hash match</small>}</div>
      <button className="icon-button" title="Preview file" aria-label={`Preview ${file.name}`} onClick={() => api.preview(file.path).catch(e => onError(errorText(e)))}><Eye size={17}/></button>
      <button className="icon-button" title="Reveal in Finder" aria-label={`Reveal ${file.name}`} onClick={() => api.reveal(file.path).catch(e => onError(errorText(e)))}><FolderOpen size={17}/></button>
    </div>)}{group.files.length > limit && <button className="text-button show-more" onClick={() => setLimit(n => n+24)}>Show more files ({group.files.length-limit} remaining)</button>}
  </article>;
}
export default function GhostHunt({ available }) {
  const operation = useJob('scan'), { job, busy, error, setError } = operation;
  const [folder, setFolder] = useState(null), [threshold,setThreshold] = useState(8), [visual,setVisual] = useState(true);
  const [selected,setSelected] = useState(new Set()), [filter,setFilter] = useState('exact'), [page,setPage] = useState(0);
  const [cleaning,setCleaning] = useState(false), [message,setMessage] = useState('');
  const result = job?.state === 'done' ? job.result : null;
  const groups = result?.groups.filter(g => g.kind === filter) || [];
  const records = useMemo(() => new Map((result?.groups || []).flatMap(g => g.files.map(f => [f.path,f]))),[result]);
  const selectionBytes = [...selected].reduce((n,path) => n+(records.get(path)?.size || 0),0);
  const disabled = busy || cleaning || !available;
  function accept(files) {
    if (!files.length) return;
    if (files.length !== 1 || !files[0].directory) throw new Error('Drop or select one folder to scan.');
    setFolder(files[0]); setSelected(new Set()); setMessage(''); operation.reset(); setPage(0);
  }
  async function choose() { try { accept(await api.choose('scan')); } catch(e) { setError(errorText(e)); } }
  function scan() { setSelected(new Set()); setMessage(''); setPage(0); operation.start([folder.path], {threshold,visual}); }
  function toggle(path) { setSelected(old => { const next = new Set(old); next.has(path) ? next.delete(path) : next.add(path); return next; }); }
  async function trash() {
    setCleaning(true); setError('');
    try {
      const response = await api.trash(job.id, [...selected]);
      if (!response.cancelled) {
        setSelected(new Set());
        if (response.moved.length) { operation.reset(); setMessage(`${response.moved.length} file(s) moved to Trash. Scan again to refresh the results. Trash can be restored in Finder.`); }
        if (response.errors.length) setError(response.errors.map(item => `${item.path}: ${item.error}`).join('\n'));
      }
    } catch(e) { setError(errorText(e)); }
    finally { setCleaning(false); }
  }
  return <section className="section ghost-section">
    <SectionHeading label="02 / GHOST HUNT" title="Find what’s hiding." subtitle="Uncover duplicate files and familiar-looking images."><span className="tag">Nothing removed automatically</span></SectionHeading>
    <Notice onClose={() => setError('')}>{error}</Notice><Notice tone="success" onClose={() => setMessage('')}>{message}</Notice>
    <Dropzone className="scan-controls panel" disabled={disabled} onFiles={accept} onError={setError}>
      <button className="folder-target" onClick={choose} disabled={disabled}><span className="folder-icon"><Folder size={24}/></span><span><strong>{folder?.name || 'Choose a folder'}</strong><small title={folder?.path}>{folder?.path || 'Or drop a folder anywhere in this box'}</small></span></button>
      <div className="scan-settings"><label className="checkbox-label"><input type="checkbox" checked={visual} disabled={disabled} onChange={e => setVisual(e.target.checked)}/>Find similar images</label><div className="between"><small>Strict</small><small>Broader · {threshold} bits</small></div><input aria-label="Similarity distance" type="range" min="0" max="16" value={threshold} disabled={disabled || !visual} onChange={e => setThreshold(Number(e.target.value))}/></div>
      <button className="button primary" disabled={disabled || !folder} onClick={scan}><ScanLine size={16}/>{result ? 'Scan again' : 'Start scan'}</button>
    </Dropzone>
    <p className="fine-print scan-note">Similarity is measured against each group’s reference image using a 64-bit pHash. A match is a candidate, not proof of identical content. TIFF/GIF checks use the first frame.</p>
    {busy && <Progress job={job} cancel={operation.cancel}/>}
    {job?.state === 'cancelled' && <Notice tone="info">Scan cancelled. No files were changed.</Notice>}
    {!result && !busy && <div className="ghost-empty"><div className="ghost-illustration"><div/><div/><Ghost size={56} strokeWidth={1}/></div><h2>A place for everything.<br/><span>Just one of everything.</span></h2><p>Exact copies are checked byte for byte with SHA-256.<br/>Similar images are yours to review.</p><div className="row muted"><Check size={14}/>Local scanning <span>·</span> Manual cleanup <span>·</span> Recoverable Trash</div></div>}
    {result && <>
      <div className="stats-grid"><div className="panel stat"><small>FILES SCANNED</small><strong>{result.filesScanned.toLocaleString()}</strong></div><div className="panel stat"><small>GROUPS FOUND</small><strong>{result.exactGroups+result.similarGroups}<span>{result.exactGroups} exact · {result.similarGroups} similar</span></strong></div><div className="panel stat"><small>EXACT DUPLICATE POTENTIAL</small><strong className="mint">{bytes(result.recoverableBytes)}</strong></div></div>
      <p className="fine-print">Logical file sizes, not guaranteed disk savings. Hard links are excluded; APFS clones and filesystem allocation may differ. Space is freed only after emptying Trash.</p>
      {(result.errorCount > 0 || result.symlinksSkipped > 0 || result.hardlinksSkipped > 0 || result.skipped > 0) && <details className="scan-warnings"><summary>{result.errorCount} scan issues · {result.symlinksSkipped} symbolic links · {result.hardlinksSkipped} hard links · {result.skipped} special files skipped</summary><ul>{result.warnings.map((warning,i) => <li key={i}>{warning}</li>)}</ul><p>Symbolic links and hard-linked files are intentionally excluded.</p></details>}
      <div className="results-toolbar"><div className="segmented filter-tabs">{[['exact','Exact copies',result.exactGroups],['similar','Similar images',result.similarGroups]].map(([value,label,count]) => <button key={value} onClick={() => {setFilter(value);setPage(0);}} aria-pressed={filter === value} className={filter === value ? 'selected' : ''}>{label}<span>{count}</span></button>)}</div><button className="text-button" disabled={cleaning || !result.exactGroups} onClick={() => setSelected(new Set(result.groups.filter(g => g.kind === 'exact').flatMap(g => g.files.slice(1).map(f => f.path))))}>Select extra exact copies</button></div>
      {filter === 'similar' && <Notice tone="info">These images may differ in resolution, edits or content. Percentages show hash agreement, not the probability of a duplicate. No visual matches are selected automatically.</Notice>}
      {groups.length === 0 ? <div className="empty-results"><Check size={25}/><h3>{filter === 'exact' ? 'No exact duplicates found.' : 'No visually similar groups found.'}</h3><p>{filter === 'similar' ? 'Try a broader threshold and scan again.' : 'A little less clutter to think about.'}</p></div> : groups.slice(page*8,page*8+8).map(group => <Group key={job.id+group.id} group={group} jobId={job.id} selected={selected} toggle={toggle} onError={setError} disabled={cleaning}/>)}
      {groups.length > 8 && <div className="pagination"><button className="icon-button" aria-label="Previous groups" disabled={page===0} onClick={() => setPage(n=>n-1)}><ChevronLeft size={18}/></button><span>Page {page+1} of {Math.ceil(groups.length/8)}</span><button className="icon-button" aria-label="Next groups" disabled={(page+1)*8>=groups.length} onClick={() => setPage(n=>n+1)}><ChevronRight size={18}/></button></div>}
      <div className="cleanup-bar"><div><strong>{selected.size} selected</strong><small>{bytes(selectionBytes)} · keep at least one per group</small></div><div className="row"><button className="text-button" disabled={cleaning || !selected.size} onClick={() => setSelected(new Set())}>Clear selection</button><button className="button danger" disabled={cleaning || !selected.size} onClick={trash}><Trash2 size={16}/>{cleaning ? 'Verifying…' : 'Move to Trash…'}</button></div></div>
    </>}
  </section>;
}
