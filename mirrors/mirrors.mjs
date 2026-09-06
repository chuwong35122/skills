#!/usr/bin/env node
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PORTS = { FIRST: 8787, LAST: 8796 };
const HERE = dirname(fileURLToPath(import.meta.url));

const CAPABILITY = { image: "page-as-img", pdf: "page-as-pdf" };

function configDir() {
	if (process.env.CLAUDE_CONFIG_DIR) return join(process.env.CLAUDE_CONFIG_DIR, "mirrooors");
	if (process.env.CODEX_HOME) return join(process.env.CODEX_HOME, "mirrooors");
	return join(homedir(), ".claude", "mirrooors");
}

function loadPairing() {
	const dir = configDir();
	const file = join(dir, "agent.json");
	try {
		return { file, ...JSON.parse(readFileSync(file, "utf8")) };
	} catch {
		mkdirSync(dir, { recursive: true, mode: 0o700 });
		const pairing = { pairingKey: randomBytes(32).toString("hex"), port: PORTS.FIRST };
		writeFileSync(file, JSON.stringify(pairing, null, 2), { mode: 0o600 });
		return { file, ...pairing };
	}
}

async function bridgeAt(port, pairingKey) {
	const response = await fetch(`http://127.0.0.1:${port}/pair`).catch(() => null);
	if (!response?.ok) return false;
	const body = await response.json().catch(() => ({}));
	return body.pairingKey === pairingKey;
}

function bridgeErrorText(body) {
	try {
		return JSON.parse(body).error ?? null;
	} catch {
		return null;
	}
}

async function readResult(response) {
	if (response.ok) return response.json();

	const detail = await response.text().catch(() => "");
	const reason = bridgeErrorText(detail) ?? `HTTP ${response.status}`;
	return { ok: false, error: `The bridge refused the request: ${reason}` };
}

function spawnBridge(port, pairingKey) {
	const child = spawn(
		process.execPath,
		[join(HERE, "bridge.mjs"), `--port=${port}`, `--key=${pairingKey}`],
		{ detached: true, stdio: ["ignore", "pipe", "pipe"] },
	);
	return new Promise((done) => {
		child.stdout.once("data", () => done(child));
		child.once("exit", () => done(null));
		setTimeout(() => done(null), 5_000);
	});
}

async function ensureBridge(pairing) {
	for (let port = PORTS.FIRST; port <= PORTS.LAST; port += 1) {
		if (await bridgeAt(port, pairing.pairingKey)) return { port, started: null };
		const child = await spawnBridge(port, pairing.pairingKey);
		if (child) {
			child.unref();
			return { port, started: child };
		}
	}
	throw new Error(
		`No free port in ${PORTS.FIRST}-${PORTS.LAST}. Something else is holding the whole range.`,
	);
}

function buildRequest(mode, url) {
	const target = url ? { url } : {};
	if (mode === "ping") return { type: "mirrooors:ping" };
	if (mode === "md") return { type: "mirrooors:extract", ...target };
	return {
		type: "mirrooors:capture",
		...target,
		settings: { capabilities: [CAPABILITY[mode]], imageFormat: "png" },
	};
}

function writeExports(data, outDir) {
	mkdirSync(outDir, { recursive: true });
	return data.exports.map((item) => {
		const path = join(outDir, item.filename);
		const [, base64] = item.dataUrl.split(",");
		writeFileSync(path, Buffer.from(base64, "base64"));
		return path;
	});
}

const [mode, ...rest] = process.argv.slice(2);
if (!["md", "image", "pdf", "ping"].includes(mode)) {
	console.error("usage: mirrors.mjs <md|image|pdf|ping> [url] [--out <dir>]");
	process.exit(2);
}

const outFlag = rest.indexOf("--out");
const outDir = outFlag === -1 ? resolve(".") : resolve(rest[outFlag + 1]);
const url = rest[0] && !rest[0].startsWith("--") ? rest[0] : undefined;

const pairing = loadPairing();
const bridge = await ensureBridge(pairing);

try {
	const response = await fetch(`http://127.0.0.1:${bridge.port}/request`, {
		method: "POST",
		headers: { "content-type": "application/json", "x-mirrooors-key": pairing.pairingKey },
		body: JSON.stringify(buildRequest(mode, url)),
	});
	const result = await readResult(response);

	if (!result.ok) {
		console.error(result.error);
		process.exitCode = 1;
	} else if (result.type === "capture") {
		console.log(JSON.stringify({ ok: true, files: writeExports(result.data, outDir) }, null, 2));
	} else if (result.type === "extract") {
		const path = join(outDir, "page.md");
		mkdirSync(outDir, { recursive: true });
		writeFileSync(path, result.data.markdown);
		console.log(JSON.stringify({ ok: true, file: path, title: result.data.title }, null, 2));
	} else {
		console.log(JSON.stringify(result, null, 2));
	}
} finally {
	if (bridge.started) {
		try {
			process.kill(bridge.started.pid);
		} catch (error) {
			void error;
		}
	}
}
