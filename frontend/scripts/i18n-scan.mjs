import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const srcDir = path.join(rootDir, 'src');
const targets = [];

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
      continue;
    }
    if (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) {
      targets.push(full);
    }
  }
}

function indexToLine(content, index) {
  return content.slice(0, index).split('\n').length;
}

function addMatches(content, filePath, regex, label, findings) {
  for (const match of content.matchAll(regex)) {
    const line = indexToLine(content, match.index ?? 0);
    findings.push(`${filePath}:${line} ${label}`);
  }
}

walk(srcDir);

const findings = [];
for (const filePath of targets) {
  const content = fs.readFileSync(filePath, 'utf8');
  const relative = path.relative(rootDir, filePath);

  addMatches(content, relative, /showToast\(\s*['"`]/g, 'Avoid raw string in showToast(...)', findings);
  addMatches(content, relative, /showAlert\(\s*['"`]/g, 'Avoid raw string in showAlert(...)', findings);
  addMatches(
    content,
    relative,
    /set\w+Status\(\s*\{[\s\S]*?message\s*:\s*(['"`])(?:(?!\1)[\s\S])*?[A-Za-z가-힣](?:(?!\1)[\s\S])*?\1[\s\S]*?\}\s*\)/g,
    'Avoid raw string in set*Status({ message: ... })',
    findings
  );
}

if (findings.length > 0) {
  console.error('i18n scan failed:\n');
  for (const finding of findings) console.error(`- ${finding}`);
  process.exit(1);
}

console.log('i18n scan passed.');
