import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const rootDir = process.cwd();
const localeFiles = {
  en: path.join(rootDir, 'src/i18n/locales/en/common.ts'),
  ko: path.join(rootDir, 'src/i18n/locales/ko/common.ts'),
};

function parseLocaleObject(filePath) {
  const sourceText = fs.readFileSync(filePath, 'utf8');
  const source = ts.createSourceFile(filePath, sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);

  let objectLiteral = null;
  for (const stmt of source.statements) {
    if (!ts.isVariableStatement(stmt)) continue;
    for (const decl of stmt.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name)) continue;
      if (!decl.name.text.endsWith('Common')) continue;
      if (decl.initializer && ts.isAsExpression(decl.initializer) && ts.isObjectLiteralExpression(decl.initializer.expression)) {
        objectLiteral = decl.initializer.expression;
      } else if (decl.initializer && ts.isObjectLiteralExpression(decl.initializer)) {
        objectLiteral = decl.initializer;
      }
    }
  }

  if (!objectLiteral) {
    throw new Error(`Unable to parse locale object in ${filePath}`);
  }
  return objectLiteral;
}

function collectKeys(node, prefix = '', output = new Set()) {
  if (!ts.isObjectLiteralExpression(node)) return output;
  for (const prop of node.properties) {
    if (!ts.isPropertyAssignment(prop)) continue;
    const name = ts.isIdentifier(prop.name)
      ? prop.name.text
      : ts.isStringLiteral(prop.name)
        ? prop.name.text
        : null;
    if (!name) continue;
    const keyPath = prefix ? `${prefix}.${name}` : name;
    output.add(keyPath);
    if (ts.isObjectLiteralExpression(prop.initializer)) {
      collectKeys(prop.initializer, keyPath, output);
    }
  }
  return output;
}

const enKeys = collectKeys(parseLocaleObject(localeFiles.en));
const koKeys = collectKeys(parseLocaleObject(localeFiles.ko));

const missingInKo = [...enKeys].filter((k) => !koKeys.has(k)).sort();
const missingInEn = [...koKeys].filter((k) => !enKeys.has(k)).sort();

if (missingInKo.length || missingInEn.length) {
  console.error('i18n key sync failed.\n');
  if (missingInKo.length) {
    console.error('Missing in ko:');
    for (const key of missingInKo) console.error(`- ${key}`);
    console.error('');
  }
  if (missingInEn.length) {
    console.error('Missing in en:');
    for (const key of missingInEn) console.error(`- ${key}`);
    console.error('');
  }
  process.exit(1);
}

console.log(`i18n keys are in sync (${enKeys.size} paths).`);
