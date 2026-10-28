// Tooling only. Read workspace exports without modifying the source checkout
// or depending on its package-manager symlink layout.
import { registerHooks } from 'node:module';
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export function sourceLoader(sourceRoot) {
  const packages = new Map();
  for (const directory of readdirSync(join(sourceRoot, 'packages'))) {
    const root = join(sourceRoot, 'packages', directory);
    let manifest;
    try { manifest = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')); }
    catch (error) { if (error.code === 'ENOENT') continue; throw error; }
    packages.set(manifest.name, { root, manifest });
  }
  return registerHooks({
    resolve(specifier, context, next) {
      if (!specifier.startsWith('@fple/')) return next(specifier, context);
      const [scope, name, ...tail] = specifier.split('/');
      const pkg = packages.get(`${scope}/${name}`);
      if (!pkg) throw new Error(`Unknown source package ${specifier}`);
      const key = tail.length ? `./${tail.join('/')}` : '.';
      let target = pkg.manifest.exports?.[key];
      if (target === undefined) {
        for (const [pattern, value] of Object.entries(pkg.manifest.exports ?? {})) {
          const [start, end] = pattern.split('*');
          if (!pattern.includes('*') || !key.startsWith(start) || !key.endsWith(end)) continue;
          const replacement = key.slice(start.length, key.length - end.length);
          target = typeof value === 'string' ? value.replace('*', replacement) : value;
          break;
        }
      }
      if (typeof target === 'object') target = target.import ?? target.default;
      if (typeof target !== 'string') throw new Error(`Source export unavailable: ${specifier}`);
      return next(pathToFileURL(resolve(pkg.root, target)).href, context);
    },
  });
}
