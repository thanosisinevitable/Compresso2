import { useState } from 'react';
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowUpRight, Binary, ChartNoAxesColumnIncreasing, File, Info, Plus } from 'lucide-react';
import { api, bytes, Dropzone, errorText, Notice, Progress, SectionHeading, useJob } from './ui';

function FrequencyTooltip({ active, payload, total }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return <div className="chart-tooltip"><strong>0x{item.byte.toString(16).padStart(2,'0').toUpperCase()} · {item.byte}</strong><span>{item.count.toLocaleString()} occurrences</span><small>{total ? (item.count/total*100).toFixed(3) : '0.000'}% of bytes</small></div>;
}
function EntropyMeter({ value }) {
  const circumference = 2*Math.PI*77;
  return <div className="entropy-meter" role="img" aria-label={value === null ? 'Entropy undefined for empty file' : `Entropy ${value.toFixed(4)} out of 8 bits per byte`}>
    <svg viewBox="0 0 190 190"><defs><linearGradient id="entropy-gradient" x1="0" y1="1" x2="1" y2="0"><stop stopColor="#6e6593"/><stop offset="1" stopColor="#d8caff"/></linearGradient></defs><circle cx="95" cy="95" r="77" fill="none" stroke="#242229" strokeWidth="9"/><circle cx="95" cy="95" r="77" fill="none" stroke="url(#entropy-gradient)" strokeWidth="9" strokeLinecap="round" transform="rotate(-90 95 95)" strokeDasharray={circumference} strokeDashoffset={circumference*(1-(value ?? 0)/8)} className="meter-fill"/></svg>
    <div><strong>{value === null ? '—' : value.toFixed(3)}</strong><span>bits / byte</span></div><span className="meter-min">0</span><span className="meter-max">8</span>
  </div>;
}
export default function EntropyLab({ available }) {
  const operation = useJob('entropy'), { job, busy, error, setError } = operation;
  const [file,setFile] = useState(null), [chunk,setChunk] = useState(null);
  const result = job?.state === 'done' ? job.result : null;
  const disabled = busy || !available;
  function accept(files) {
    if (!files.length) return;
    if (files.length !== 1 || files[0].directory) throw new Error('Choose one file of any type. Folders cannot be analyzed.');
    setFile(files[0]); setChunk(null); operation.start([files[0].path]);
  }
  async function choose() { try { accept(await api.choose('entropy')); } catch(e) { setError(errorText(e)); } }
  const distribution = result?.frequencies.map((count,byte) => ({byte,count,frequency:result.size ? count/result.size*100 : 0})) || [];
  const selectedChunk = chunk ?? result?.chunks[0];
  return <section className="section entropy-section">
    <SectionHeading label="03 / ENTROPY LAB" title="Look beneath the file." subtitle="Discover the patterns, probabilities and surprises in your data."><span className="tag lavender">H(X) = −Σ p(x) log₂ p(x)</span></SectionHeading>
    <Notice onClose={() => setError('')}>{error}</Notice>
    <Dropzone className="panel entropy-file" onFiles={accept} onError={setError} disabled={disabled}>
      <span className="file-icon"><File size={23}/></span><div className="grow"><strong>{file?.name || 'Every file has a story.'}</strong><small title={file?.path}>{file ? `${bytes(file.size)} · ${result?.type || file.path}` : 'Drop any file to read its information content. Nothing is modified.'}</small></div><button className="button secondary" onClick={choose} disabled={disabled}><Plus size={15}/>{file ? 'Change file' : 'Choose a file'}</button>
    </Dropzone>
    {busy && <Progress job={job} cancel={operation.cancel}/>}
    {job?.state === 'cancelled' && <Notice tone="info">Analysis cancelled. Your file is unchanged.</Notice>}
    {!result && !busy && <div className="entropy-empty panel"><div className="empty-data-art" aria-hidden="true">{Array.from({length:48},(_,i)=><i key={i} style={{height:`${20 + Math.sin(i*2.7)**2*75}%`,opacity:.2+i/95}}/>)}</div><div className="empty-lab-content"><span className="lab-icon"><Binary size={29}/></span><h2>A closer look at information.</h2><p>Explore byte entropy, frequency and local patterns.<br/>Read the entire file, one manageable chunk at a time.</p><div className="lab-promises"><span>01 <strong>Entropy meter</strong></span><span>02 <strong>Byte distribution</strong></span><span>03 <strong>Entropy heatmap</strong></span></div></div></div>}
    {result && <>
      <div className="entropy-grid">
        <div className="panel meter-panel"><div className="between"><h3>Shannon entropy</h3><Info size={15} className="muted" aria-label="Empirical byte entropy from 0 to 8 bits per byte"/></div><EntropyMeter value={result.entropy}/><div className="meter-caption">{result.entropy === null ? 'No bytes to analyze' : result.entropy >= 7.5 ? 'High byte-level uncertainty' : result.entropy >= 5 ? 'Moderate byte-level uncertainty' : 'Low byte-level uncertainty'}</div><div className="redundancy"><span>Statistical redundancy<small>100 × (1 − H / 8)</small></span><strong>{result.redundancy === null ? '—' : `${result.redundancy.toFixed(1)}%`}</strong></div></div>
        <div className="panel histogram-panel"><div className="between"><div><h3>Byte distribution</h3><p>Frequency of each possible byte value.</p></div><ChartNoAxesColumnIncreasing size={18} className="muted"/></div>
          <div className="histogram"><ResponsiveContainer width="100%" height="100%" minWidth={0}><BarChart data={distribution} margin={{top:10,right:8,bottom:2,left:0}} barCategoryGap={0} accessibilityLayer>
            <CartesianGrid vertical={false} stroke="#26232d" strokeDasharray="3 5"/><XAxis dataKey="byte" ticks={[0,32,64,96,128,160,192,224,255]} interval={0} tick={{fill:'#92909b',fontSize:10}} axisLine={false} tickLine={false}/><YAxis width={45} tickFormatter={n=>`${n}%`} tick={{fill:'#92909b',fontSize:10}} axisLine={false} tickLine={false}/><Tooltip content={<FrequencyTooltip total={result.size}/>} cursor={{fill:'#ffffff10'}}/><Bar dataKey="frequency" fill="#b8a4df" isAnimationActive={false} radius={[1,1,0,0]}/>
          </BarChart></ResponsiveContainer></div><div className="chart-caption"><span>BYTE VALUE · DECIMAL</span><span>{result.size.toLocaleString()} bytes counted</span></div>
        </div>
      </div>
      <div className="panel heatmap-panel"><div className="between heatmap-heading"><div><h3>Entropy across the file</h3><p>Consecutive sections, from the first byte to the last.</p></div><div className="heatmap-legend"><span>Predictable</span><i/><span>Varied</span><small>0–8 bits/byte</small></div></div>
        {result.chunks.length ? <div className="heatmap">{result.chunks.map(item=><button key={item.index} style={{background:`hsl(264 35% ${14+item.entropy/8*61}%)`}} className={selectedChunk?.index===item.index ? 'active' : ''} aria-label={`Section ${item.index+1}, offset ${item.offset}, ${item.size} bytes, entropy ${item.entropy.toFixed(4)}`} title={`Section ${item.index+1}: ${item.entropy.toFixed(4)} bits/byte`} onMouseEnter={()=>setChunk(item)} onFocus={()=>setChunk(item)} onClick={()=>setChunk(item)}/>)}</div> : <p className="empty-heatmap">No chunks: this file is empty.</p>}
        <div className="heatmap-detail">{selectedChunk ? <><span>SECTION <strong>{String(selectedChunk.index+1).padStart(3,'0')}</strong></span><span>OFFSET <strong>{selectedChunk.offset.toLocaleString()} B</strong></span><span>SIZE <strong>{bytes(selectedChunk.size)}</strong></span><span>ENTROPY <strong className="lavender-text">{selectedChunk.entropy.toFixed(4)} bits/byte</strong></span></> : <span>No values to display</span>}</div>
        <small>Up to 256 sections · {bytes(result.chunkSize)} per full section · small sections may show lower empirical entropy.</small>
      </div>
      <div className="insight-panel"><span className="insight-icon"><Binary size={20}/></span><div><div className="eyebrow">WHAT YOUR DATA SAYS</div><p>{result.explanation}</p><small>The redundancy estimate describes the byte distribution. It is not a guaranteed percentage of removable data.</small></div><ArrowUpRight size={18} className="muted"/></div>
    </>}
  </section>;
}
