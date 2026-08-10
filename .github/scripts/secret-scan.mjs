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
 *   3. No STAGED BLOB contains anything shaped like key material. Read §A.
 *   4. `.env.example`, if present, carries names and no values. It is the file
 *      whose whole job is to be safe to commit, which is exactly why it is the
 *      one that gets a real value pasted into it.
 *
 * ── §A. THE SCANNER READS THE INDEX, NOT THE DISK (J28-C1) ────────────────
 * This previously enumerated paths with `git ls-files` — the INDEX — and read
 * their bytes with `readFileSync` — the DISK. `git commit` writes the index.
 * Jury staged a live key, reverted the worktree, and got:
 *
 *     index has key: 1 | worktree has key: 0
 *     secret-scan: clean — 0 findings          exit 0
 *
 * On this machine `doc-check`'s [STAGED] guard happened to catch the
 * divergence. On any clone without `resources/`, `doc-check` exits 2 and runs
 * NO checks at all, and CI treats 2 as a pass — so on every contributor's
 * machine that key ships. This is the same defect as round 22's Critical and
 * round 27's Critical (**read from staged blobs**), reproduced inside the one
 * file whose subject is four live API keys.
 *
 * Content now comes from `git show :<path>`, which is the exact bytes a commit
 * would write. `--all` additionally reads untracked files from disk, because an
 * untracked file HAS no staged blob — that is a local sweep, not the gate.
 *
 * ── §B. RULES ARE KEYED ON VALUE SHAPE, NOT ON VARIABLE NAME (J28-M1) ─────
 * Two of the four real keys had no vendor rule. Their only coverage was
 * `assigned-secret`, which required an UPPERCASE variable name — so a key in an
 * `Authorization: Bearer` header, or in a lowercase `api_key = "..."` (this
 * project's own Python idiom), passed clean. A rule that depends on how the
 * developer NAMED the variable is a rule that tests style, not secrecy.
 *
 * Every vendor rule below matches the VALUE. `bearer-literal` and
 * `assigned-secret-anycase` cover the two carrier syntaxes that have no name to
 * key on. All are proven against synthetic keys by `--self-test`.
 *
 * WHAT IT NEVER DOES
 * Print a match. A scanner that echoes the secret it found has moved that secret
 * into the CI log, where it is more exposed than it was. Findings name the file,
 * the line, and the RULE — never the value.
 *
 * USAGE  node .github/scripts/secret-scan.mjs [--all] [--self-test]
 *        --all       also scans untracked files from disk (local pre-commit sweep)
 *        --self-test proves each rule catches a synthetic key, and proves the
 *                    index/worktree divergence above, by EXECUTION in a scratch
 *                    git repository. Touches neither this repo's index nor disk.
 * EXIT   0 clean · 1 findings · 2 not a git repository
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, statSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// ── Rules ────────────────────────────────────────────────────────────────
// Each rule is (name, regex, why). The regexes are written so that this file
// does not match itself — verified by the fact that this scanner scans this
// scanner. There is no self-exemption: a scanner that skips its own source is a
// scanner with one file nobody checks. `--self-test` therefore builds its
// synthetic keys by CONCATENATION at runtime; a literal one pasted here would
// be caught by this scanner scanning itself, which is correct behaviour and
// would also make the file unstageable.
const RULES = [
  ['openrouter-key', /\bsk-or-v1-[0-9a-f]{24,}/g,
    'OpenRouter API key'],
  ['fish-audio-key', /\bsk-fish-[A-Za-z0-9_-]{16,}/g,
    'Fish Audio API key'],
  ['hypereal-key', /\bck_[0-9a-f]{48,}/g,
    'Hypereal API key (ck_ + 64 hex)'],
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
  // ── The three name-independent rules (J28-M1) ──────────────────────────
  // Lemonfox issues a BARE 32-char mixed-case alphanumeric token: no prefix, no
  // separator, nothing to anchor a vendor rule to. The only signal is the shape
  // of the value itself. Requiring BOTH cases AND a digit is what keeps this off
  // hex digests (lowercase only — every SHA-256 in this repo's manifests) and
  // off the base32/uppercase constants that appear in fixtures.
  ['bare-credential-token', /(?<![A-Za-z0-9_/+-])(?=[A-Za-z0-9]{28,48}(?![A-Za-z0-9]))(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{28,48}/g,
    'a bare token shaped like a generated credential — 28-48 chars, mixed case, with digits'],
  // The carrier syntax that has no variable name at all.
  ['bearer-literal', /\b(?:Bearer|Basic|Token)\s+["'`]?([A-Za-z0-9_\-.=+/]{20,})/g,
    'a literal credential in an Authorization-style header'],
  // The generic shape: a secret-ish NAME assigned a long literal value. Now
  // CASE-INSENSITIVE on the name — `api_key = "..."` is this project's Python
  // idiom and was the exact string that passed both gates clean.
  //
  // The VALUE class is credential characters, not "anything that is not a
  // delimiter" (J29-C2). The permissive form matched a line of ordinary
  // JavaScript that assigns a parsed value to a variable named `token`: the
  // name hits the alternation and the value ran exactly 16 characters — the
  // floor — before the first `(`. So the [TREE-MARKER] repair for J28-M3
  // tripped the J28-M1 repair inside the same commit, and CI went red on a
  // file containing no key material at all.
  //
  // The FIRST narrowing over-corrected (J30-M3). It used [A-Za-z0-9_\-.=+/]
  // and justified itself with "no vendor issues keys containing parentheses" —
  // which reasons only about VENDOR-ISSUED keys, while this rule's own name
  // alternation also matches `password`, `passwd`, `secret` and `auth`, whose
  // values are HUMAN-CHOSEN and routinely contain `! @ # % & :`. Because the
  // first 16 characters must all be in class, one special character early in
  // the string defeated the rule outright, and five realistic password shapes
  // the permissive version caught went missing. A comment asserting a coverage
  // property the code does not have is this repository's own definition of an
  // attestation rather than a control.
  //
  // The class below admits password punctuation and still excludes the
  // brackets, parentheses, backslashes and whitespace that make a value CODE
  // rather than a secret — so `body.split(/` still stops at the `(` after ten
  // characters. Every one of the five shapes is a trial in --self-test.
  ['assigned-secret-anycase', /\b[A-Za-z0-9_]*(?:api[_-]?key|secret|token|password|passwd|private[_-]?key|access[_-]?key|auth)\s*[:=]\s*["'`]?([A-Za-z0-9_\-.=+/!@#$%^&*:~?]{16,})/gi,
    'a secret-shaped name assigned a literal value (any case)'],
];

// Values that are obviously not secrets. Kept SHORT and specific: a permissive
// placeholder list is how a real key gets waved through for containing the
// letters "test".
const PLACEHOLDER = /^(?:\$\{|process\.env|os\.environ|<|your[-_]|xxx|changeme|replace[-_]me|example|placeholder|redacted|\.\.\.|"")/i;

// Binary and evidence. The SPIKE A audio is committed on purpose (J23-M5) and is
// not text; the artifact JSONs are measurements. Scanning them for entropy would
// produce noise, and a noisy scanner is a scanner people disable.
const SKIP = [
  /\.(?:wav|mp3|png|jpg|jpeg|pdf|woff2?|ico|zip|gz)$/i,
  /(?:^|\/)pnpm-lock\.yaml$/,
  /(?:^|\/)node_modules\//,
];

const MUST_BE_IGNORED = ['.env', '.env.local', '.env.production', 'id_rsa', 'secrets.pem', '.npmrc'];

// The .env.example shape test: a property of key material rather than of length.
// A generated credential is a long run of MIXED-CASE letters WITH digits. A
// documented default is not — `postgresql://postgres:postgres@127.0.0.1:54322/postgres`,
// `development`, `8080`, `info` all survive, and they must, because a template
// with no defaults is a template that teaches nothing.
//
// J28-M1's second half: this required an uppercase letter in the VALUE, and one
// of the four real keys does not have one. A lowercase-and-digits run of 20+ is
// now equally suspect, because that is what half the vendors issue.
const KEYLIKE = /(?=[A-Za-z0-9+/_=-]{20,})(?=[A-Za-z0-9+/_=-]*[a-z])(?=[A-Za-z0-9+/_=-]*\d)[A-Za-z0-9+/_=-]{20,}/;

// ── The scan, as a function of a repository ──────────────────────────────
// Parameterised by `cwd` so `--self-test` can run the REAL logic against a
// scratch repository. A self-test that re-implements the check proves only that
// two copies of a mistake agree.
function scan({ cwd = process.cwd(), scanUntracked = false } = {}) {
  const findings = [];
  const note = (file, line, rule, why) => findings.push({ file, line, rule, why });
  const git = (args, opts = {}) =>
    execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...opts });

  let tracked;
  try {
    tracked = git(['ls-files']).split('\n').map((s) => s.trim()).filter(Boolean);
  } catch {
    return null;   // not a git repository
  }

  // ── 1. Is git enforcing the rules that protect key material? ───────────
  for (const path of MUST_BE_IGNORED) {
    try {
      git(['check-ignore', '-q', '--no-index', path]);
    } catch {
      note('.gitignore', 0, 'ignore-rule-missing',
        `git does NOT ignore ${path}. Key material is one \`git add\` from the index.`);
    }
  }
  try {
    git(['check-ignore', '-q', '--no-index', '.env.example']);
    note('.gitignore', 0, 'ignore-rule-too-broad',
      '.env.example is IGNORED. It is the file that documents variable names for ' +
      'contributors, and an ignored template is a template nobody gets.');
  } catch { /* not ignored — correct */ }

  // ── 2. Is an env file already tracked? ─────────────────────────────────
  for (const f of tracked) {
    const base = f.split('/').pop() ?? f;
    if (/^\.env(\..+)?$/.test(base) && base !== '.env.example') {
      note(f, 0, 'env-file-tracked',
        'an env file is in the index. A .gitignore rule does nothing for a file ' +
        'git already tracks — it must be removed with `git rm --cached`.');
    }
  }

  // ── 3. Content, READ FROM THE STAGED BLOB (§A) ─────────────────────────
  // `fromIndex` is the flag that decides where bytes come from. Tracked files
  // are read with `git show :<path>` — the bytes a commit would write, which is
  // the thing being gated. Untracked files under `--all` have no staged blob
  // and are read from disk, and that difference is deliberate and marked.
  const targets = tracked.map((f) => ({ file: f, fromIndex: true }));
  if (scanUntracked) {
    try {
      targets.push(...git(['ls-files', '--others', '--exclude-standard'])
        .split('\n').map((s) => s.trim()).filter(Boolean)
        .map((f) => ({ file: f, fromIndex: false })));
    } catch { /* nothing extra to add */ }
  }

  for (const { file, fromIndex } of targets) {
    if (SKIP.some((re) => re.test(file))) continue;

    let buf;
    if (fromIndex) {
      try {
        buf = execFileSync('git', ['show', `:${file}`], { cwd, maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
      } catch {
        continue;   // staged as a deletion, or a submodule/gitlink — no blob to read
      }
    } else {
      const abs = join(cwd, file);
      if (!existsSync(abs)) continue;
      try {
        if (!statSync(abs).isFile()) continue;
      } catch { continue; }
      try {
        buf = readFileSync(abs);
      } catch { continue; }
    }
    if (buf.length > 2_000_000) continue;
    if (buf.includes(0)) continue;                     // a NUL byte means binary
    const text = buf.toString('utf8');

    const lines = text.split('\n');
    for (const [name, re, why] of RULES) {
      for (const m of text.matchAll(re)) {
        const captured = m[1];
        if (captured && PLACEHOLDER.test(captured)) continue;
        // An assignment whose value is a variable reference, not a literal.
        if (captured && /^[A-Z0-9_]+$/.test(captured) && captured.length < 40) continue;
        const line = text.slice(0, m.index).split('\n').length;
        // Report the RULE and the location. Never the match.
        note(file, line, name,
          `${why} (${(lines[line - 1] ?? '').length} chars on that line` +
          `${fromIndex ? ', read from the STAGED BLOB' : ', read from disk — untracked'})`);
      }
    }
  }

  // ── 4. .env.example carries names and DEFAULTS, never key material ─────
  // Read from the index too, for the same reason as §3.
  let exampleText = null;
  if (tracked.includes('.env.example')) {
    try {
      exampleText = execFileSync('git', ['show', ':.env.example'], { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    } catch { /* fall through */ }
  }
  if (exampleText === null && existsSync(join(cwd, '.env.example'))) {
    exampleText = readFileSync(join(cwd, '.env.example'), 'utf8');
  }
  if (exampleText !== null) {
    exampleText.split('\n').forEach((raw, i) => {
      const line = raw.trim();
      if (!line || line.startsWith('#')) return;
      const eq = line.indexOf('=');
      if (eq < 0) return;
      const value = line.slice(eq + 1).trim();
      if (!value || PLACEHOLDER.test(value)) return;
      if (!KEYLIKE.test(value)) return;
      note('.env.example', i + 1, 'example-carries-key-material',
        'the template has a value shaped like a generated credential — 20+ characters ' +
        'with digits. It is the file whose whole job is to be safe to commit, ' +
        'which is why it is the one a real key lands in.');
    });
  }

  return { findings, fileCount: targets.length };
}

// ── Self-test ────────────────────────────────────────────────────────────
// Every trial is a MUTATION: plant a synthetic key, assert this scanner catches
// it. A guard with no mutation proving it fires is a guard nobody has tested,
// which is how [ART-FIGURE] sat vacuous for twelve documents.
//
// The synthetic keys are built by concatenation so that no literal in this
// source matches a rule. They are structurally valid and cryptographically
// worthless.
function selfTest() {
  const hex = (n) => 'abcdef0123456789'.repeat(20).slice(0, n);
  const K = {
    // Shapes mirror the four real vendors. None is a real key.
    openrouter: 'sk-or-' + 'v1-' + hex(64),
    fish: 'sk-' + 'fish-' + 'aB3dE6gH9jK2mN5pQ8sT1vW4yZ7',
    hypereal: 'ck' + '_' + hex(64),
    // Lemonfox: 32 chars, mixed case, digits, NO prefix — the shape that had no
    // rule and passed both gates in J28-M1.
    // Split, for the reason the header gives: written as one literal this is a
    // 32-char mixed-case-with-digits run, and `bare-credential-token` catches it
    // in this file -- which it DID on the first run, correctly. The scanner
    // scanning its own source is the property that keeps it honest, so the
    // specimen bends and the rule does not.
    lemonfox: 'aB3dE6gH9jK2' + 'mN5pQ8sT1vW4' + 'yZ7cX0fU',
  };

  const trials = [
    // — §B: value-shape rules, in the carriers that defeated the old scanner —
    ['lemonfox key in a lowercase `api_key =` (the project idiom)',
      `api_key = "${K.lemonfox}"\n`, true],
    ['lemonfox key in an Authorization: Bearer header',
      `headers = {"Authorization": "Bearer ${K.lemonfox}"}\n`, true],
    ['lemonfox key bare, with no name at all',
      `curl -H 'X-Api: ${K.lemonfox}' https://example.invalid\n`, true],
    ['hypereal key in a lowercase assignment',
      `hypereal_key = '${K.hypereal}'\n`, true],
    ['hypereal key in a Bearer header',
      `Authorization: Bearer ${K.hypereal}\n`, true],
    ['openrouter key', `OPENROUTER_API_KEY=${K.openrouter}\n`, true],
    ['fish audio key', `fish = "${K.fish}"\n`, true],
    ['openrouter key with NO variable name, in prose',
      `the key we used was ${K.openrouter} and it is now rotated\n`, true],
    // — negatives: a scanner that flags everything gets switched off —
    ['a lowercase sha-256 digest is not a credential',
      `"sha256": "${hex(64)}"\n`, false],
    ['a documented default survives',
      'DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres\n', false],
    ['an env var reference survives',
      'API_KEY=${OPENROUTER_API_KEY}\n', false],
    ['a placeholder survives', 'FISH_AUDIO_API_KEY=your-key-here\n', false],
    ['a uuid survives (fish reference_id, all over the fixtures)',
      '"reference_id": "a5d7dcbb81b4472ea0e240af3edaae7d"\n', false],
    ['prose with a long word survives',
      'The transcription instrumentation demonstrated reproducibility.\n', false],
    // J29-C2 — the exact shape that turned CI red on a clean file. `token`
    // matches the name alternation; the old value class ran to the 16-char
    // floor before the `(`. Pinned as a trial because a false positive is how
    // a scanner gets allowlisted, and an allowlisted scanner is not a control.
    ['ordinary code assigning to a variable named `token` survives',
      'const token = body.split(/' + '\\s+/)[0] || "";\n', false],
    ['a regex assigned to `secret_pattern` survives',
      'secret_pattern = re.compile(r"[A-Za-z0-9]{32}")\n', false],
    // KEYLIKE was widened this round to accept lowercase-and-digits because one
    // of the four real keys has no uppercase letter. This asserts the rule list
    // agrees with it, so the two halves cannot drift apart again (J29-m1).
    ['a lowercase-and-digits credential is caught (KEYLIKE parity)',
      'auth = "' + 'a1b2c3d4e5f6g7h8j9k0m1n2p3q4r5s6' + '"\n', true],
    // J30-M3 — the five shapes the first narrowing dropped. All are HUMAN-CHOSEN
    // secrets, which is what `password`/`passwd`/`secret`/`auth` in the name
    // alternation are for, and all contain punctuation a vendor key never would.
    ['a password with & and - is caught',
      'DB_PASSWORD = "Tr0ub4dor' + '&3-xKcd-Sec9"\n', true],
    ['a password with @ and ! is caught',
      'password: "S3cureP' + '@ssw0rd!LongEnough123"\n', true],
    ['a password with # is caught',
      'passwd="aB3' + '#kQ9zLmX2vN8pR4tY"\n', true],
    ['a colon-separated credential is caught',
      'auth = "admin' + ':sup3rl0ngpassw0rdvalue"\n', true],
    ['a percent-encoded client secret is caught',
      'client_secret: "x9K' + '%2FvB8nQ4mZ7wL3pT6"\n', true],
  ];

  const root = mkdtempSync(join(tmpdir(), 'secret-scan-selftest-'));
  const run = (args, cwd) => execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  let passed = 0, failed = 0;
  const fail = (name, detail) => { failed++; console.log(`  FAIL  ${name}\n        ${detail}`); };
  const ok = (name) => { passed++; console.log(`  ok    ${name}`); };

  const newRepo = () => {
    const dir = mkdtempSync(join(root, 'r-'));
    run(['init', '-q'], dir);
    run(['config', 'user.email', 's@t.invalid'], dir);
    run(['config', 'user.name', 'selftest'], dir);
    // Match the real repo's ignore rules so the §1 checks do not add noise.
    writeFileSync(join(dir, '.gitignore'),
      '.env\n.env.local\n.env.production\nid_rsa\nsecrets.pem\n.npmrc\n');
    run(['add', '.gitignore'], dir);
    return dir;
  };

  console.log('secret-scan --self-test\n');
  console.log('  § rule mutations — each plants a synthetic key and asserts a finding\n');
  for (const [name, content, shouldCatch] of trials) {
    const dir = newRepo();
    writeFileSync(join(dir, 'planted.py'), content);
    run(['add', 'planted.py'], dir);
    const r = scan({ cwd: dir });
    const hit = r.findings.some((f) => f.file === 'planted.py');
    if (hit === shouldCatch) ok(name);
    else fail(name, shouldCatch
      ? 'planted a synthetic key and the scanner did NOT flag it'
      : `flagged a benign value: ${r.findings.filter((f) => f.file === 'planted.py').map((f) => f.rule).join(', ')}`);
  }

  // — §A: the Critical itself, reproduced and then proven fixed —
  console.log('\n  § J28-C1 — the index/worktree divergence, by execution\n');
  {
    const dir = newRepo();
    writeFileSync(join(dir, 'planted.py'), `api_key = "${K.lemonfox}"\n`);
    run(['add', 'planted.py'], dir);
    // The exact move Jury made: stage the key, then revert the WORKTREE.
    writeFileSync(join(dir, 'planted.py'), 'api_key = os.environ["LEMONFOX_API_KEY"]\n');

    const onDisk = readFileSync(join(dir, 'planted.py'), 'utf8').includes(K.lemonfox);
    const inIndex = run(['show', ':planted.py'], dir).includes(K.lemonfox);
    if (inIndex && !onDisk) ok('scenario built: key IS in the index, NOT on disk');
    else fail('scenario built', `index=${inIndex} disk=${onDisk} — the test itself is wrong`);

    const r = scan({ cwd: dir });
    if (r.findings.some((f) => f.file === 'planted.py')) {
      ok('the staged key is caught (reading the disk would have missed it)');
    } else {
      fail('staged-blob read', 'the key is in the blob a commit would write and the scanner passed it — J28-C1 is OPEN');
    }
  }

  // The inverse, which is the half that proves the first half means anything:
  // a key on DISK but NOT staged must NOT fail the gate, or the gate is just
  // noise and gets disabled.
  {
    const dir = newRepo();
    writeFileSync(join(dir, 'clean.py'), 'x = 1\n');
    run(['add', 'clean.py'], dir);
    writeFileSync(join(dir, 'clean.py'), `api_key = "${K.lemonfox}"\n`);   // unstaged edit
    const r = scan({ cwd: dir });
    if (!r.findings.some((f) => f.file === 'clean.py')) {
      ok('an UNSTAGED key does not fail the gate (it is not what ships)');
    } else {
      fail('unstaged tolerance', 'flagged a key that is not in the index — the gate would cry wolf');
    }
    // …but `--all` is the local sweep, and it SHOULD see it.
    const r2 = scan({ cwd: dir, scanUntracked: true });
    writeFileSync(join(dir, 'untracked.py'), `api_key = "${K.lemonfox}"\n`);
    const r3 = scan({ cwd: dir, scanUntracked: true });
    if (!r2.findings.some((f) => f.file === 'untracked.py') &&
        r3.findings.some((f) => f.file === 'untracked.py')) {
      ok('--all catches an UNTRACKED file, which has no staged blob to read');
    } else {
      fail('--all untracked', 'the local sweep did not pick up an untracked key');
    }
  }

  rmSync(root, { recursive: true, force: true });
  console.log(`\n${passed + failed} trials · ${passed} passed · ${failed} failed`);
  if (failed) {
    console.log('\nA failing trial means this scanner does not catch what it claims to.');
    process.exit(1);
  }
  process.exit(0);
}

// ── Main ─────────────────────────────────────────────────────────────────
if (process.argv.includes('--self-test')) selfTest();

const result = scan({ cwd: process.cwd(), scanUntracked: process.argv.includes('--all') });
if (result === null) {
  console.error('secret-scan: not a git repository (or git is unavailable).');
  process.exit(2);
}
const { findings, fileCount } = result;

if (!findings.length) {
  console.log('secret-scan: clean — 0 findings');
  console.log(`  ${fileCount} file(s) scanned FROM THE INDEX · ${RULES.length} content rules · ` +
    `${MUST_BE_IGNORED.length} ignore rules asked of git directly`);
  console.log('  values are never printed; findings name the file, the line and the rule');
  console.log('  run --self-test to prove the rules fire');
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
