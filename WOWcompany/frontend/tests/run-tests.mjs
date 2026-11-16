import { build } from 'esbuild'
import { spawnSync } from 'node:child_process'
import { unlinkSync } from 'node:fs'
const out='tests/recommendations.compiled.mjs'
try {
 await build({entryPoints:['tests/recommendations.test.jsx'],outfile:out,bundle:true,packages:'external',platform:'node',format:'esm',jsx:'automatic'})
 const r=spawnSync(process.execPath,['--test',out],{stdio:'inherit'});process.exitCode=r.status??1
} finally {try{unlinkSync(out)}catch{}}
