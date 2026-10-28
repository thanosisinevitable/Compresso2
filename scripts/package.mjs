import { spawnSync } from 'node:child_process';
import path from 'node:path';
if(process.platform!=='darwin'){console.error('Build .app and .dmg on macOS. This command deliberately refuses to produce an unverified cross-platform bundle.');process.exit(1);}
const arch=process.argv.includes('--x64')?'x64':process.argv.includes('--arm64')?'arm64':process.arch;
if(!['arm64','x64'].includes(arch)||arch!==process.arch){console.error('Use matching native Node and Python architectures. Build arm64 on Apple Silicon or x64 on Intel.');process.exit(1);}
function run(args){const result=spawnSync(process.execPath,args,{stdio:'inherit',env:{...process.env,COMPRESSO_BUILD_ARCH:arch}});if(result.error)throw result.error;if(result.status!==0)process.exit(result.status??1);}
run(['scripts/python.mjs','scripts/build_backend.py']);
run([path.resolve('node_modules/vite/bin/vite.js'),'build']);
run([path.resolve('node_modules/electron-builder/cli.js'),'--mac',`--${arch}`]);
