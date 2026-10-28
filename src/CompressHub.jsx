import { useState } from 'react';
import { Archive, ArrowDownToLine, Crosshair } from 'lucide-react';
import Compress from './Compress';
import TargetLock from './TargetLock';
import VersionVault from './VersionVault';
import { SectionHeading } from './ui';
export default function CompressHub({available}){
  const [mode,setMode]=useState('standard');
  return <section className="section compress-hub"><SectionHeading label="01 / COMPRESS" title="Make room for more." subtitle="Smaller files. Smarter choices. Every version accounted for."><span className="tag">Originals preserved</span></SectionHeading><nav className="compress-modes" aria-label="Compression tools">{[['standard','Standard',ArrowDownToLine],['target','Target Lock',Crosshair],['vault','Version Vault',Archive]].map(([id,label,Icon])=><button key={id} className={mode===id?'active':''} aria-current={mode===id?'page':undefined} onClick={()=>setMode(id)}><Icon size={15}/>{label}</button>)}</nav><div hidden={mode!=='standard'}><Compress available={available} embedded/></div><div hidden={mode!=='target'}><TargetLock available={available}/></div><div hidden={mode!=='vault'}><VersionVault available={available}/></div></section>;
}
