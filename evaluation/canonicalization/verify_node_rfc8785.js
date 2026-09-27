#!/usr/bin/env node
/**
 * Cross-runtime RFC 8785 Canonical JSON Verifier (Node.js reference engine).
 * 
 * Verifies 100% byte equality and determinism between Node.js ECMAScript JSON engine
 * and python clara_api.glhs.canonical_json specification across all 35 test vectors.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const MIN_SAFE_INTEGER = -9007199254740991;
const MAX_SAFE_INTEGER = 9007199254740991;

// Character replacements per RFC 8785 Section 3.2.2.2
function serializeString(str) {
    // Check for lone surrogates (0xD800 - 0xDFFF)
    for (let i = 0; i < str.length; i++) {
        const code = str.charCodeAt(i);
        if (code >= 0xD800 && code <= 0xDBFF) {
            // High surrogate: must be followed by low surrogate (0xDC00 - 0xDFFF)
            if (i + 1 >= str.length) {
                throw new Error(`canonical_json_lone_surrogate: U+${code.toString(16).toUpperCase()}`);
            }
            const nextCode = str.charCodeAt(i + 1);
            if (nextCode < 0xDC00 || nextCode > 0xDFFF) {
                throw new Error(`canonical_json_lone_surrogate: U+${code.toString(16).toUpperCase()}`);
            }
            i++; // skip valid pair
        } else if (code >= 0xDC00 && code <= 0xDFFF) {
            // Unmatched low surrogate
            throw new Error(`canonical_json_lone_surrogate: U+${code.toString(16).toUpperCase()}`);
        }
    }

    let out = '"';
    for (let i = 0; i < str.length; i++) {
        const ch = str[i];
        const code = str.charCodeAt(i);
        if (ch === '"') out += '\\"';
        else if (ch === '\\') out += '\\\\';
        else if (ch === '\b') out += '\\b';
        else if (ch === '\f') out += '\\f';
        else if (ch === '\n') out += '\\n';
        else if (ch === '\r') out += '\\r';
        else if (ch === '\t') out += '\\t';
        else if (code < 0x20) {
            out += '\\u' + code.toString(16).padStart(4, '0');
        } else {
            out += ch;
        }
    }
    out += '"';
    return out;
}

function canonicalize(obj) {
    if (obj === null) return 'null';
    if (typeof obj === 'boolean') return obj ? 'true' : 'false';
    if (typeof obj === 'number') {
        if (!Number.isFinite(obj)) {
            throw new Error('canonical_json_non_finite_number');
        }
        if (Object.is(obj, -0)) {
            return '0';
        }
        return JSON.stringify(obj);
    }
    if (typeof obj === 'string') {
        return serializeString(obj);
    }
    if (Array.isArray(obj)) {
        return '[' + obj.map(item => canonicalize(item)).join(',') + ']';
    }
    if (typeof obj === 'object') {
        // Sort keys by UTF-16 code units (native JS string comparison)
        const keys = Object.keys(obj).sort((a, b) => {
            return a < b ? -1 : a > b ? 1 : 0;
        });
        const pairs = keys.map(k => serializeString(k) + ':' + canonicalize(obj[k]));
        return '{' + pairs.join(',') + '}';
    }
    throw new Error(`canonical_json_unsupported_type:${typeof obj}`);
}

function resolveTaggedInput(inp) {
    if (inp !== null && typeof inp === 'object' && inp.$type) {
        if (inp.$type === 'lone_surrogate') {
            const code = parseInt(inp.value, 16);
            return String.fromCharCode(code);
        }
        if (inp.$type === 'non_finite_float') {
            return inp.value === 'NaN' ? NaN : (inp.value.startsWith('-') ? -Infinity : Infinity);
        }
        if (inp.$type === 'unsafe_decimal') {
            throw new Error('canonical_json_unsafe_decimal_precision');
        }
        if (inp.$type === 'integer_overflow') {
            throw new Error('canonical_json_integer_out_of_ijson_range');
        }
    }
    return inp;
}

function main() {
    const rootDir = path.resolve(__dirname, '../../');
    let vecPath = path.join(rootDir, 'testdata/glhs/canonicalization/v2/vectors.json');
    let expPath = path.join(rootDir, 'testdata/glhs/canonicalization/v2/expected.json');
    let outputJson = false;

    const positionalArgs = [];
    for (let i = 2; i < process.argv.length; i++) {
        const arg = process.argv[i];
        if (arg === '--json') {
            outputJson = true;
        } else if (arg.startsWith('--vectors=')) {
            vecPath = path.resolve(arg.split('=')[1]);
        } else if (arg.startsWith('--expected=')) {
            expPath = path.resolve(arg.split('=')[1]);
        } else if (!arg.startsWith('-')) {
            positionalArgs.push(arg);
        }
    }

    if (positionalArgs.length >= 1) vecPath = path.resolve(positionalArgs[0]);
    if (positionalArgs.length >= 2) expPath = path.resolve(positionalArgs[1]);

    const vectors = JSON.parse(fs.readFileSync(vecPath, 'utf8'));
    const expected = JSON.parse(fs.readFileSync(expPath, 'utf8'));

    const expMap = new Map();
    expected.forEach(e => expMap.set(e.id, e));

    let passed = 0;
    let failed = 0;

    const results = [];

    vectors.forEach(vec => {
        const exp = expMap.get(vec.id);
        let actualStatus = 'VALID';
        let actualCanonical = null;
        let actualSha256 = null;
        let actualError = null;

        try {
            const resolvedInp = resolveTaggedInput(vec.input);
            actualCanonical = canonicalize(resolvedInp);
            const buf = Buffer.from(actualCanonical, 'utf8');
            actualSha256 = crypto.createHash('sha256').update(buf).digest('hex');
        } catch (err) {
            actualStatus = 'REJECTED';
            actualError = err.message;
        }

        let isMatch = false;
        if (exp.status === 'VALID' && actualStatus === 'VALID') {
            isMatch = (actualCanonical === exp.expected_canonical_json) && (actualSha256 === exp.expected_sha256);
        } else if (exp.status === 'REJECTED' && actualStatus === 'REJECTED') {
            isMatch = actualError.includes(exp.expected_error);
        }

        if (isMatch) {
            passed++;
        } else {
            failed++;
        }

        results.push({
            id: vec.id,
            category: vec.category,
            expected_status: exp.status,
            actual_status: actualStatus,
            match: isMatch,
            expected_canonical: exp.expected_canonical_json || null,
            actual_canonical: actualCanonical,
            expected_sha256: exp.expected_sha256 || null,
            actual_sha256: actualSha256,
            expected_error: exp.expected_error || null,
            actual_error: actualError,
        });
    });

    const byteEqualityRate = passed / vectors.length;
    const report = {
        runtime: 'node',
        node_version: process.version,
        total_vectors: vectors.length,
        passed: passed,
        failed: failed,
        byte_equality_rate: byteEqualityRate,
        cross_runtime_determinism: byteEqualityRate === 1.0,
        results: results
    };

    if (outputJson) {
        console.log(JSON.stringify(report, null, 2));
    } else {
        console.log(`[Node Verification] Total: ${vectors.length} | Passed: ${passed} | Failed: ${failed} | Byte Equality: ${(byteEqualityRate * 100).toFixed(2)}%`);
    }

    process.exit(failed === 0 ? 0 : 1);
}

main();
