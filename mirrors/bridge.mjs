#!/usr/bin/env node
import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { createServer } from "node:http";

const HOLD_MS = 25_000;
const IDLE_MS = 90_000;
const TASK_TIMEOUT_MS = 180_000;

const args = new Map(
	process.argv.slice(2).map((pair) => {
		const [flag, value] = pair.split("=");
		return [flag.replace(/^--/, ""), value ?? "true"];
	}),
);

const pairingKey = args.get("key");
const port = Number(args.get("port"));
if (!pairingKey || !Number.isInteger(port)) {
	console.error("usage: bridge.mjs --key=<pairing key> --port=<port>");
	process.exit(2);
}

const sessionId = randomUUID();
const startedAt = Date.now();
const sessionKey = createHmac("sha256", pairingKey).update(`${sessionId}:${startedAt}`).digest();

const proofFor = (message) => createHmac("sha256", sessionKey).update(message).digest("hex");

function verified(url) {
	const nonce = url.searchParams.get("nonce");
	const proof = url.searchParams.get("proof");
	if (!nonce || !proof) return false;
	const expected = Buffer.from(proofFor(nonce), "utf8");
	const given = Buffer.from(proof, "utf8");
	return expected.length === given.length && timingSafeEqual(expected, given);
}

const queue = [];
const inFlight = new Map();
let waiting = null;
let idleTimer = null;

function handOut() {
	if (!waiting || queue.length === 0) return;
	const deliver = waiting;
	waiting = null;
	deliver(queue.shift());
}

function resetIdle() {
	clearTimeout(idleTimer);
	idleTimer = setTimeout(() => process.exit(0), IDLE_MS);
}

function readBody(request) {
	return new Promise((resolve, reject) => {
		let body = "";
		request.on("data", (chunk) => {
			body += chunk;
		});
		request.on("end", () => resolve(body));
		request.on("error", reject);
	});
}

function send(response, status, payload) {
	if (payload === undefined) {
		response.writeHead(status).end();
		return;
	}
	const body = JSON.stringify(payload);
	response.writeHead(status, {
		"content-type": "application/json",
		"content-length": Buffer.byteLength(body),
	});
	response.end(body);
}

const server = createServer(async (request, response) => {
	const url = new URL(request.url, `http://127.0.0.1:${port}`);

	if (url.pathname === "/pair") {
		send(response, 200, { pairingKey, port });
		return;
	}

	if (url.pathname === "/health") {
		const nonce = url.searchParams.get("nonce");
		if (!nonce) {
			send(response, 400, { error: "nonce required" });
			return;
		}
		send(response, 200, { sessionId, startedAt, proof: proofFor(`server:${nonce}`) });
		return;
	}

	if (url.pathname === "/request") {
		if (request.headers["x-mirrooors-key"] !== pairingKey) {
			send(response, 401, { ok: false, error: "Bad key." });
			return;
		}
		resetIdle();

		const task = { id: randomUUID(), request: JSON.parse(await readBody(request)) };
		const result = await new Promise((resolve) => {
			const timer = setTimeout(() => {
				inFlight.delete(task.id);
				resolve({ ok: false, error: "The extension did not answer in time." });
			}, TASK_TIMEOUT_MS);

			inFlight.set(task.id, (value) => {
				clearTimeout(timer);
				resolve(value);
			});
			queue.push(task);
			handOut();
		});

		send(response, 200, result);
		return;
	}

	if (!verified(url)) {
		send(response, 401, { error: "Bad proof." });
		return;
	}

	if (url.pathname === "/next") {
		if (queue.length > 0) {
			send(response, 200, queue.shift());
			return;
		}
		const task = await new Promise((resolve) => {
			waiting = resolve;
			setTimeout(() => {
				if (waiting === resolve) {
					waiting = null;
					resolve(null);
				}
			}, HOLD_MS);
		});
		if (!task) {
			send(response, 204);
			return;
		}
		send(response, 200, task);
		return;
	}

	if (url.pathname === "/result") {
		const body = JSON.parse(await readBody(request));
		const reply = inFlight.get(body.id);
		if (reply) {
			inFlight.delete(body.id);
			reply(body.response);
		}
		send(response, 200, { ok: true });
		return;
	}

	send(response, 404, { error: "Unknown route." });
});

server.listen(port, "127.0.0.1", () => {
	resetIdle();
	console.log(JSON.stringify({ port, sessionId, pid: process.pid }));
});

server.on("error", (error) => {
	console.error(error.code === "EADDRINUSE" ? "EADDRINUSE" : error.message);
	process.exit(1);
});
