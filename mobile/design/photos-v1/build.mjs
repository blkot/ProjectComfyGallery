// Build the self-contained design preview. No backend or package install is required.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const here = path.dirname(fileURLToPath(import.meta.url));
const deps = process.env.COMFY_DESIGN_NODE_MODULES || '/Users/wangshenhao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const names = ['Big Sur Coastline','Big Sur Mountains','Catalina Sunset','Big Sur Waters Edge','Big Sur Night Grasses','Big Sur Road','Catalina Clouds','Catalina Rock','Catalina Shoreline','Big Sur Night Succulents','Big Sur Horizon','Big Sur Aerial'];
const assetDir = path.join(here,'assets');
fs.mkdirSync(assetDir,{recursive:true});
const media = names.map((name,i)=>{
  const output = path.join(assetDir,`sample-${String(i+1).padStart(2,'0')}.jpg`);
  if(!fs.existsSync(output)) execFileSync('/usr/bin/sips',['-s','format','jpeg','-s','formatOptions','72','-Z','720',`/System/Library/Desktop Pictures/.thumbnails/${name}.heic`,'--out',output],{stdio:'pipe'});
  return `data:image/jpeg;base64,${fs.readFileSync(output).toString('base64')}`;
});
const appIcon=fs.readFileSync(path.join(here,'../../ComfyGalleryMobile/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png')).toString('base64');
const template=fs.readFileSync(path.join(here,'prototype.fragment.html'),'utf8');
const fragment=template.replace('__MEDIA_DATA__',JSON.stringify(media)).replace('__APP_ICON__',`data:image/png;base64,${appIcon}`);
if(Buffer.byteLength(fragment)>1_000_000) throw new Error('Inline design exceeds the size budget');
const lucide=fs.readFileSync(path.join(deps,'lucide/dist/umd/lucide.min.js'),'utf8').replaceAll('</script','<\\/script');
const shell=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Comfy Gallery · iOS 相册式重构设计 V1</title><style>:root{color-scheme:light dark}body{margin:0;background:light-dark(#f1f2f4,#18181b)}.viz-dotted-background{background-image:radial-gradient(light-dark(#c9cbd1,#424248) .65px,transparent .65px);background-size:18px 18px}button{cursor:pointer}</style><script>${lucide}</script></head><body>${fragment}</body></html>`;
fs.writeFileSync(path.join(here,'index.html'),shell);
const inlinePath=process.argv[2];
if(inlinePath)fs.writeFileSync(inlinePath,fragment);
console.log(JSON.stringify({preview:path.join(here,'index.html'),inline:inlinePath||null,bytes:Buffer.byteLength(fragment),sampleCount:media.length}));
