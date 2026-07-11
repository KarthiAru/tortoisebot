import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { extname, join } from 'node:path';

const root = process.cwd();
const dist = join(root, 'dist');
const packageJson = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));

function gitCommit() {
  try {
    return execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return 'unknown';
  }
}

function walk(dir) {
  const files = [];
  for (const item of readdirSync(dir)) {
    const path = join(dir, item);
    const stat = statSync(path);
    if (stat.isDirectory()) files.push(...walk(path));
    else files.push(path);
  }
  return files;
}

const version = {
  name: packageJson.name,
  version: packageJson.version,
  build_time: new Date().toISOString(),
  git_commit: gitCommit(),
  frontend_stack: 'svelte-typescript-vite-tailwind',
};

writeFileSync(join(dist, 'portal-version.json'), JSON.stringify(version, null, 2) + '\n');

const compressible = new Set(['.html', '.css', '.js', '.json', '.svg', '.txt']);
for (const file of walk(dist)) {
  if (!compressible.has(extname(file))) continue;
  const source = readFileSync(file);
  const compressed = gzipSync(source, { level: 9 });
  if (compressed.length < source.length) {
    writeFileSync(`${file}.gz`, compressed);
  }
}

const assets = [];
for (const file of walk(dist)) {
  if (file.endsWith('portal-assets.json')) continue;
  const relative = file.slice(dist.length + 1).replaceAll('\\', '/');
  const source = readFileSync(file);
  assets.push({
    path: relative,
    bytes: source.length,
    sha256: createHash('sha256').update(source).digest('hex'),
    gzip: relative.endsWith('.gz'),
  });
}
assets.sort((a, b) => a.path.localeCompare(b.path));
writeFileSync(join(dist, 'portal-assets.json'), JSON.stringify({
  generated_at: new Date().toISOString(),
  asset_count: assets.length,
  total_bytes: assets.reduce((total, asset) => total + asset.bytes, 0),
  assets,
}, null, 2) + '\n');

