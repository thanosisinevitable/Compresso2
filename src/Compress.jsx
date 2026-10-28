import { useState } from 'react';
import { ArrowDown, ArrowDownToLine, ArrowUpRight, Check, ChevronDown, FileStack, Plus, Eye } from 'lucide-react';
import ArtifactLens from './ArtifactLens';
import { api, bytes, Dropzone, errorText, Notice, Progress, Rings, SectionHeading, useJob } from './ui';

export default function Compress({ available, embedded = false }) {
  const [files, setFiles] = useState([]), [pdfQuality, setQuality] = useState('Extreme');
  const [outputFormat, setFormat] = useState('original'), [pdfDpi, setDpi] = useState(150);
  const [saved, setSaved] = useState(''), [saving, setSaving] = useState(false);
  const [lens,setLens] = useState(null);
  const operation = useJob('compress');
  const { job, error, setError, busy } = operation;
  const result = job?.state === 'done' ? job.result : null;
  const disabled = busy || saving || !available;
  const converting = outputFormat !== 'original';
  const rasterizing = converting && outputFormat !== 'pdf' && files.some(file => /\.(pdf|zip)$/i.test(file.name));
  const showPdfPresets = !files.length ? !converting : (!converting || outputFormat === 'pdf') && files.some(file => /\.(pdf|zip)$/i.test(file.name));
  const formatNotes = {
    original: 'Compress each file in its original format. PNG transparency and TIFF pages are retained.',
    png: 'Lossless PNG images with transparency. Multipage inputs become one image per page in a ZIP.',
    jpg: 'Full-resolution JPEG at quality 85. Transparency becomes white; each page becomes an image.',
    tiff: 'Lossless Deflate TIFF. All pages from each document stay together in a multipage TIFF.',
    webp: 'Lossless WebP with transparency. Multipage inputs become one image per page in a ZIP.',
    bmp: 'Uncompressed RGB bitmap. Transparency becomes white; each page becomes an image.',
    pdf: 'One PDF per source file, retaining all its pages. Multiple documents are returned in a ZIP.',
  };
  function accept(records) {
    if (!records.length) return;
    if (records.some(f => f.directory || !/\.(png|jpe?g|tiff?|webp|bmp|pdf|zip)$/i.test(f.name))) throw new Error('Choose PNG, JPG, TIFF, WebP, BMP, PDF, or one ZIP archive.');
    if (records.some(f => /\.zip$/i.test(f.name)) && records.length > 1) throw new Error('Choose one ZIP at a time, or select individual files.');
    setFiles(records); setSaved(''); operation.reset();
  }
  const choose = async () => { try { accept(await api.choose('compress')); } catch (reason) { setError(errorText(reason)); } };
  async function save() {
    setSaving(true); setError('');
    try { const path = await api.save(job.id); if (path) setSaved(path); }
    catch (reason) { setError(errorText(reason)); }
    finally { setSaving(false); }
  }
  return <section className="section compress-section">
    {!embedded && <SectionHeading label="01 / COMPRESS" title="Make room for more." subtitle="Smaller files. A little more breathing room."><span className="tag"><span className="status-dot"/>Originals preserved</span></SectionHeading>}
    <Notice onClose={() => setError('')}>{error}</Notice>
    <div className="compress-grid">
      <Dropzone className="compress-drop" onFiles={accept} onError={setError} disabled={disabled}>
        <div className="drop-content">
          <div className="drop-orbit">
            <Rings active={busy}/>
            <button className={`orb ${result ? 'complete' : ''}`} onClick={result ? save : choose} disabled={disabled} aria-label={result ? 'Save compressed output' : 'Choose files to compress'}>
              {result ? <Check size={29}/> : <ArrowDown size={29}/>}</button>
          </div>
          <h2>{busy ? (converting ? 'A new format is on its way.' : 'A lighter version is on its way.') : result ? 'Your files are ready.' : files.length ? `${files.length} file${files.length > 1 ? 's' : ''} ready` : 'Drop the weight.'}</h2>
          <p>{busy ? 'Processing on your Mac.' : result ? `${result.outputCount} output file${result.outputCount !== 1 ? 's' : ''} · ${bytes(result.outputBytes)}` : 'Drag files here, or choose from Finder.'}</p>
          {!busy && !result && <button className="button secondary" onClick={choose} disabled={disabled}><Plus size={16}/>{files.length ? 'Change files' : 'Choose files'}</button>}
        </div>
        <div className="format-line">PNG <i/> JPG <i/> TIFF <i/> WEBP <i/> BMP <i/> PDF <i/> ZIP</div>
      </Dropzone>
      <div className="compression-options">
        {showPdfPresets && <div className="panel option-panel"><div className="between"><h3>PDF compression</h3><span className="micro-label">QUALITY</span></div><p>Choose the balance of size and detail.</p>
          <div className="quality-grid">{[['Extreme','Smallest · 72 dpi'],['High','Balanced · 150 dpi'],['Medium','Print · 300 dpi'],['Low','Higher fidelity']].map(([value, label]) =>
            <button key={value} className={`choice ${pdfQuality === value ? 'selected' : ''}`} onClick={() => { setQuality(value); setSaved(''); operation.reset(); }} disabled={disabled} aria-pressed={pdfQuality === value}><strong>{value}</strong><small>{label}</small>{pdfQuality === value && <Check size={13}/>}</button>)}</div>
          <small>PDF presets can reduce image quality.</small>
        </div>}
        <div className="panel option-panel"><div className="between"><h3>Convert to</h3><span className="micro-label">OUTPUT FORMAT</span></div>
          <div className="format-select-wrap">
            <select className="format-select" aria-label="Output format" value={outputFormat} onChange={event => { setFormat(event.target.value); setSaved(''); operation.reset(); }} disabled={disabled}>
              {[['original','Keep original'],['png','PNG'],['jpg','JPG'],['tiff','TIFF'],['webp','WebP'],['bmp','BMP'],['pdf','PDF']].map(([value,label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <ChevronDown className="format-select-chevron" size={15} aria-hidden="true"/>
          </div>
          <p className="option-description">{formatNotes[outputFormat]}</p>
          {rasterizing && <label className="pdf-resolution">PDF image resolution<div className="format-select-wrap"><select className="format-select" aria-label="PDF image resolution" value={pdfDpi} onChange={event => { setDpi(Number(event.target.value)); setSaved(''); operation.reset(); }} disabled={disabled}>{[72,150,300].map(dpi => <option key={dpi} value={dpi}>{dpi} dpi</option>)}</select><ChevronDown className="format-select-chevron" size={15} aria-hidden="true"/></div><small>PDF pages become images; text is rasterized.</small></label>}
        </div>
        <p className="fine-print">{converting ? 'Conversion preserves source files and image dimensions. PDF page dimensions depend on your selected dpi. Conversions can create larger files.' : 'JPG compression uses quality 75 and a maximum 1920 px edge. ZIP archives may contain mixed supported formats.'}</p>
      </div>
    </div>
    {files.length > 0 && !busy && !result && <div className="file-selection panel"><FileStack size={20}/><div className="grow"><strong>{files.length === 1 ? files[0].name : `${files.length} selected files`}</strong><small className="truncate" title={files.map(f => f.path).join('\n')}>{files.length > 1 ? files.slice(0,3).map(f => f.name).join(', ') + (files.length > 3 ? '…' : '') : files[0].path}</small></div><span className="muted">{bytes(files.reduce((n,f) => n+f.size,0))}</span><button className="button primary" disabled={disabled} onClick={() => { setSaved(''); operation.start(files.map(f => f.path), {pdfQuality,outputFormat,pdfDpi}); }}>{converting ? 'Convert files' : 'Compress files'}<ArrowDownToLine size={16}/></button></div>}
    {busy && <Progress job={job} cancel={operation.cancel}/>}
    {job?.state === 'cancelled' && <Notice tone="info">Processing cancelled. Your originals are untouched.</Notice>}
    {result && <div className="panel result-panel"><div className="result-numbers"><div><small>INPUT CONTENT</small><strong>{bytes(result.inputBytes)}</strong></div><span className="muted">→</span><div><small>OUTPUT</small><strong>{bytes(result.outputBytes)}</strong></div><span className="tag accent">{result.outputBytes < result.inputBytes ? `${((1-result.outputBytes/result.inputBytes)*100).toFixed(1)}% smaller` : result.outputBytes === result.inputBytes ? 'Already optimized' : 'Converted output'}</span></div>
      <div className="row"><button className="text-button" disabled={saving} onClick={() => { setFiles([]); setSaved(''); operation.reset(); }}>Start again</button><button className="button primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save as…'}<ArrowDownToLine size={16}/></button></div>
      {(result.unchanged > 0 || result.skipped > 0) && <p className="fine-print full-width">{result.unchanged > 0 && `${result.unchanged} file(s) were already smaller; original bytes were retained. `}{result.skipped > 0 && `${result.skipped} unsupported or hidden ZIP entries were skipped.`}</p>}
      {saved && <div className="saved-line full-width"><Check size={15}/><span className="truncate">Saved: {saved}</span><button className="text-button" onClick={() => api.reveal(saved).catch(e => setError(errorText(e)))}>Show in Finder<ArrowUpRight size={13}/></button></div>}
    </div>}
    {result?.lensPairs?.length>0&&<div className="lens-output-list panel"><div><h3>Artifact Lens</h3><p>Inspect the visual cost of your compression.</p></div>{result.lensPairs.map((pair,i)=><button key={i} className="button secondary" onClick={()=>setLens({id:job.id,index:i})}><Eye size={15}/>{result.lensPairs.length===1?'Inspect image':pair.name}</button>)}</div>}
    {lens&&<ArtifactLens parentId={lens.id} index={lens.index} onClose={()=>setLens(null)}/>}
  </section>;
}
