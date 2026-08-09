#!/usr/bin/env node
/**
 * secret-scan — key material must never be one typo away from a commit.
 *
 * WHY THIS EXISTS, SPECIFICALLY
 * Four live provider keys (OpenRouter, Lemonfox, Fish Audio, Hypereal) were
 * pasted into a chat during Phase 0 and written to `.env`. `.env` is gitignored,
 * so nothing was committed — but that outcome was INCIDENTAL. It depended on one
 * line of `.gitignore` being right and on nobody using `git add -f`, and neither
 * of those is a control. This makes it a check.
 *
 * WHAT IT CHECKS
 *   1. The ignore rules that protect key material are actually in force, asked
 *      of git itself rather than read out of `.gitignore` — `git check-ignore`
 *      answers what git will DO, which is the only thing that matters.
 *   2. No env file carrying secrets is tracked. A gitignored file that is
 *      already in the index stays tracked forever; the ignore rule does nothing.
 *   3. No TRACKED file contains anything shaped like key material.
 *   4. `.env.example`, if present, carries names and no values. It is the file
 *      whose whole job is to be safe to commit, which is exactly why it is the
 *      one that gets a real value pasted into it.
 *
 * WHAT IT NEVER DOES
 * Print a match. A scanner that echoes the secret it found has moved that secret
 * into the CI log, where it is more exposed than it was. Findings name the file,
 * the line, and the RULE — never the value.
 *
 * USAGE  node .github/scripts/secret-scan.mjs [--all]
 *        --all also scans files git does not track, for a local pre-commit sweep.
 * EXIT   0 clean · 1 findings · 2 not a git repository
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, statSync } from 'node:fs';

const SCAN_UNTRACKED = process.argv.includes('--all');

// ── Rules ────────────────────────────────────────────────────────────────
// Each rule is (name, regex, why). The regexes are written so that this file
// does not match itself — verified by the fact that this scanner scans this
// scanner. There is no self-exemption: a scanner that skips its own source is a
// scanner with one file nobody checks.
const RULES = [
  ['openrouter-key', /\bsk-or-v1-[0-9a-f]{24,}/g,
    'OpenRouter API key'],
  ['openai-style-key', /\bsk-(?:proj-|live-)?[A-Za-z0-9_-]{32,}/g,
    'OpenAI-style secret key'],
  ['aws-access-key-id', /\bAKIA[0-9A-Z]{16}\b/g,
    'AWS access key id'],
  ['google-api-key', /\bAIza[0-9A-Za-z_-]{35}\b/g,
    'Google API key'],
  ['slack-token', /\bxox[abprs]-[0-9A-Za-z-]{10,}/g,
    'Slack token'],
  ['stripe-live-key', /\b[sr]k_live_[0-9A-Za-z]{16,}/g,
    'Stripe live key'],
  ['private-key-block', /-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----/g,
    'PEM private key'],
  ['jwt', /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\./g,
    'JSON Web Token (a Supabase service_role key is one of these)'],
  // The generic shape: a secret-ish NAME assigned a long literal value.
  ['assigned-secret', /\b[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)\s*[:=]\s*["']?([^\s"'`]{16,})/g,
    'a secret-shaped name assigned a literal value'],
];

// Values that are obviously not secrets. Kept SHORT and specific: a permissive
// placeholder list is how a real key gets waved through for containing the
// letters "test".
const PLACEHOLDER = /^(?:\$\{|process\.env|<|your[-_]|xxx|changeme|replace[-_]me|example|placeholder|redacted|\.\.\.|"")/i;

// Binary and evidence. The SPIKE A audio is committed on purpose (J23-M5) and is
// not text; the artifact JSONs are measurements. Scanning them for entropy would
// produce noise, and a noisy scanner is a scanner people disable.
const SKIP = [
  /\.(?:wav|mp3|png|jpg|jpeg|pdf|woff2?|ico|zip|gz)$/i,
  /(?:^|\/)pnpm-lock\.yaml$/,
  /(?:^|\/)node_modules\//,
];

const findings = [];
const note = (file, line, rule, why) => findings.push({ file, line, rule, why });

// ── 1. Is git enforcing the rules that protect key material? ─────────────
const git = (args) => execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
let tracked = [];
try {
  tracked = git(['ls-files']).split('\n').map((s) => s.trim()).filter(Boolean);
} catch {
  console.error('secret-scan: not a git repository (or git is unavailable).');
  process.exit(2);
}

// `git check-ignore` reports what git WILL do. Reading .gitignore reports what
// somebody wrote. The last four audits are a long argument for preferring the
// first kind of evidence.
const MUST_BE_IGNORED = ['.env', '.env.local', '.env.production', 'id_rsa', 'secrets.pem', '.npmrc'];
for (const path of MUST_BE_IGNORED) {
  try {
    git(['check-ignore', '-q', '--no-index', path]);
  } catch {
    note('.gitignore', 0, 'ignore-rule-missing',
      `git does NOT ignore ${path}. Key material is one \`git add\` from the index.`);
  }
}
// The inverse: the file whose job is to be committed must not be ignored.
try {
  git(['check-ignore', '-q', '--no-index', '.env.example']);
  note('.gitignore', 0, 'ignore-rule-too-broad',
    '.env.example is IGNORED. It is the file that documents variable names for ' +
    'contributors, and an ignored template is a template nobody gets.');
} catch { /* not ignored — correct */ }

// ── 2. Is an env file already tracked? ───────────────────────────────────
for (const f of tracked) {
  const base = f.split('/').pop() ?? f;
  if (/^\.env(\..+)?$/.test(base) && base !== '.env.example') {
    note(f, 0, 'env-file-tracked',
      'an env file is in the index. A .gitignore rule does nothing for a file ' +
      'git already tracks — it must be removed with `git rm --cached`.');
  }
}

// ── 3. Content ───────────────────────────────────────────────────────────
let files = tracked;
if (SCAN_UNTRACKED) {
  try {
    files = files.concat(
      git(['ls-files', '--others', '--exclude-standard']).split('\n').map((s) => s.trim()).filter(Boolean),
    );
  } catch { /* nothing extra to add */ }
}

for (const file of files) {
  if (SKIP.some((re) => re.test(file))) continue;
  if (!existsSync(file)) continue;
  let stat;
  try {
    stat = statSync(file);
  } catch {
    continue;
  }
  if (!stat.isFile() || stat.size > 2_000_000) continue;

  let text;
  try {
    text = readFileSync(file, 'utf8');
  } catch {
    continue;
  }
  if (text.indexOf(String.fromCharCode(0)) >= 0) continue;   // a NUL byte means binary

  const lines = text.split('\n');
  for (const [name, re, why] of RULES) {
    for (const m of text.matchAll(re)) {
      const captured = m[1];
      if (captured && PLACEHOLDER.test(captured)) continue;
      // An assignment whose value is a variable reference, not a literal.
      if (captured && /^[A-Z0-9_]+$/.test(captured) && captured.length < 40) continue;
      const line = text.slice(0, m.index).split('\n').length;
      // Report the RULE and the location. Never the match.
      note(file, line, name, `${why} (${(lines[line - 1] ?? '').length} chars on that line)`);
    }
  }
}

// ── 4. .env.example carries names and DEFAULTS, never key material ───────
// The rules above already scan this file for known key shapes, because it is a
// tracked file. This adds the shape a rule list cannot enumerate: a value that
// matches no known vendor prefix and is still a secret.
//
// The test is a property of key material rather than of length: a generated
// credential is a long run of MIXED-CASE letters WITH digits. A documented
// default is not — `postgresql://postgres:postgres@127.0.0.1:54322/postgres`,
// `development`, `8080`, `info` all survive, and they must, because a template
// with no defaults is a template that teaches nothing. Flagging every long value
// makes the check something a contributor silences.
const KEYLIKE = /(?=[A-Za-z0-9+/_=-]{20,})(?=[A-Za-z0-9+/_=-]*[a-z])(?=[A-Za-z0-9+/_=-]*[A-Z])(?=[A-Za-z0-9+/_=-]*\d)[A-Za-z0-9+/_=-]{20,}/;
if (existsSync('.env.example')) {
  const lines = readFileSync('.env.example', 'utf8').split('\n');
  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (!line || line.startsWith('#')) return;
    const eq = line.indexOf('=');
    if (eq < 0) return;
    const value = line.slice(eq + 1).trim();
    if (!value || PLACEHOLDER.test(value)) return;
    if (!KEYLIKE.test(value)) return;
    note('.env.example', i + 1, 'example-carries-key-material',
      'the template has a value shaped like a generated credential — 20+ characters, ' +
      'mixed case, with digits. It is the file whose whole job is to be safe to commit, ' +
      'which is why it is the one a real key lands in.');
  });
}

// ── Report ───────────────────────────────────────────────────────────────
if (!findings.length) {
  console.log('secret-scan: clean — 0 findings');
  console.log(`  ${files.length} file(s) scanned · ${RULES.length} content rules · ` +
    `${MUST_BE_IGNORED.length} ignore rules asked of git directly`);
  console.log('  values are never printed; findings name the file, the line and the rule');
  process.exit(0);
}
console.log(`secret-scan: ${findings.length} finding(s)\n`);
for (const f of findings) {
  console.log(`  ${f.file}:${f.line}  [${f.rule}]`);
  console.log(`    ${f.why}\n`);
}
console.log('The matched values are NOT printed. Open the file to see them.');
console.log('If a key reached a tracked file, ROTATE IT — removing the line does not');
console.log('remove it from history, and history is what gets cloned.');
process.exit(1);
