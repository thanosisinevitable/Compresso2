import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { AlertCircle, Check, File, LoaderCircle, X } from 'lucide-react';

export const api = window.compresso;
export function bytes(value) {
  if (!Number.isFinite(value)) return '—';
  if (value === 0) return '0 B';
  const exponent = Math.min(4, Math.floor(Math.log(Math.abs(value)) / Math.log(1024)));
  return `${(value / 1024 ** exponent).toLocaleString(undefined, { maximumFractionDigits: exponent ? 1 : 0 })} ${['B','KiB','MiB','GiB','TiB'][exponent]}`;
}
export function errorText(error) { return (error?.message || String(error)).replace(/^Error invoking remote method '[^']+': (Error: )?/, ''); }
export function useJob(kind) {
  const [job, setJob] = useState(null), [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const generation = useRef(0);
  const id = job?.id;
  const active = job?.state === 'running' || job?.state === 'queued';
  useEffect(() => {
    if (!id || !active) return;
    let cancelled = false, timer;
    const poll = async () => {
      try {
        const update = await api.status(id);
        if (cancelled) return;
        setJob(update);
        if (update.error) setError(update.error);
        if (['queued', 'running'].includes(update.state)) timer = setTimeout(poll, 350);
      } catch (reason) {
        if (!cancelled) { setError(errorText(reason)); setJob(old => ({ ...old, state: 'error' })); }
      }
    };
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [id, active]);
  const start = useCallback(async (paths, options = {}) => {
    const current = ++generation.current;
    setError(''); setStarting(true); setJob(null);
    try {
      const result = await api.start({ kind, paths, options });
      if (current === generation.current) setJob({ id: result.id, state: 'queued', message: 'Preparing…', current: 0, total: 0 });
    } catch (reason) { setError(errorText(reason)); }
    finally { setStarting(false); }
  }, [kind]);
  const cancel = async () => {
    try { if (id) await api.cancel(id); }
    catch (reason) { setError(errorText(reason)); }
  };
  return { job, start, cancel, busy: starting || active, error, setError, reset: () => { generation.current++; setJob(null); setError(''); } };
}
export function Notice({ children, tone = 'error', onClose }) {
  if (!children) return null;
  return <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
    {tone === 'success' ? <Check size={16}/> : <AlertCircle size={16}/>}<span>{children}</span>
    {onClose && <button className="icon-button" aria-label="Dismiss message" onClick={onClose}><X size={15}/></button>}
  </div>;
}
export function Progress({ job, cancel }) {
  const percent = job?.total ? Math.min(100, (job.current / job.total) * 100) : null;
  return <div className="progress-panel" aria-live="polite">
    <div className="between"><span className="inline"><LoaderCircle className="spin" size={16}/>{job?.message || 'Preparing…'}</span><button className="text-button" onClick={cancel}>Cancel</button></div>
    <div className={`progress-track ${percent === null ? 'indeterminate' : ''}`} role="progressbar" aria-label="Processing progress" aria-valuenow={percent ?? undefined} aria-valuemin={0} aria-valuemax={100}><div style={{ width: percent === null ? '35%' : `${percent}%` }}/></div>
    <small>{job?.total ? `${job.current.toLocaleString()} / ${job.total.toLocaleString()}` : 'Working locally. Your originals stay untouched.'}</small>
  </div>;
}
export function Dropzone({ onFiles, onError, disabled, className = '', children }) {
  const [drag, setDrag] = useState(false);
  const level = useRef(0);
  return <div className={`dropzone ${drag ? 'dragging' : ''} ${className}`} onDragEnter={e => { e.preventDefault(); level.current++; if (!disabled) setDrag(true); }}
    onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = disabled ? 'none' : 'copy'; }}
    onDragLeave={e => { e.preventDefault(); if (--level.current <= 0) { level.current = 0; setDrag(false); } }}
    onDrop={async e => {
      e.preventDefault(); setDrag(false); level.current = 0;
      if (disabled) return;
      try { if (!api) throw new Error('Open Compresso through Electron to use local files.'); await onFiles(await api.drop(Array.from(e.dataTransfer.files))); }
      catch (error) { onError(errorText(error)); }
    }}>{children}{drag && <div className="drop-overlay">Drop to add</div>}</div>;
}
export function Rings({ active = false, small = false }) {
  const reduce = useReducedMotion();
  return <div className={`rings ${small ? 'small' : ''}`} aria-hidden="true">{Array.from({length: 6}, (_, i) => <motion.div key={i}
    className="ring" style={{ width: 170 + i * 83, height: 170 + i * 83, opacity: .24 - i * .028 }}
    animate={reduce ? {} : { scale: active ? [1, 1.025, 1] : 1 }}
    transition={{ duration: active ? 3 + i * .4 : 9 + i, repeat: Infinity, ease: 'easeInOut' }}/>)}</div>;
}
export function FileThumbnail({ file, jobId }) {
  const [data, setData] = useState(null);
  const element = useRef(null);
  useEffect(() => {
    setData(null);
    if (!file.image || !api) return;
    let stopped = false;
    const observer = new IntersectionObserver(entries => {
      if (!entries[0].isIntersecting) return;
      observer.disconnect();
      api.thumbnail(jobId, file.path).then(result => { if (!stopped) setData(result.data); }).catch(() => {});
    }, { rootMargin: '100px' });
    observer.observe(element.current);
    return () => { stopped = true; observer.disconnect(); };
  }, [file.path, file.image, jobId]);
  return <div className="thumbnail" ref={element}>{data ? <img src={data} alt=""/> : <File size={21}/>}</div>;
}
export function SectionHeading({ label, title, subtitle, children }) {
  return <div className="section-heading"><div><div className="eyebrow">{label}</div><h1>{title}</h1><p>{subtitle}</p></div>{children}</div>;
}
