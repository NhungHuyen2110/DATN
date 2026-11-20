import assert from "node:assert/strict";
import test from "node:test";
import { requestJson } from "../../assets/js/shared/http-client.mjs";

test("cookies and JSON headers preserve existing session behavior", async () => {
  let sent;
  const fetchImpl = async (url, options) => {
    sent = { url, options };
    return new Response(JSON.stringify({ id: 1 }), { status: 200 });
  };
  assert.deepEqual(await requestJson("https://shop.example", "/cart", {
    method: "POST", body: "{}", headers: { "X-Test": "yes" }
  }, fetchImpl), { id: 1 });
  assert.equal(sent.url, "https://shop.example/cart");
  assert.equal(sent.options.credentials, "include");
  assert.equal(sent.options.headers["Content-Type"], "application/json");
  assert.equal(sent.options.headers["X-Test"], "yes");
});

test("204 has no JSON body", async () => {
  assert.equal(await requestJson("", "/logout", {}, async () => new Response(null, { status: 204 })), null);
});

test("server validation messages remain visible", async () => {
  await assert.rejects(requestJson("", "/cart", {}, async () => new Response(
    JSON.stringify({ detail: [{ msg: "invalid quantity" }] }), { status: 422 }
  )), /invalid quantity/);
});

test("network failure preserves the cause and a readable message", async () => {
  const cause = new TypeError("offline");
  await assert.rejects(requestJson("", "/cart", {}, async () => { throw cause; }),
    error => error.cause === cause && error.message.includes("Business API"));
});

test("non-JSON server failures report the HTTP status", async () => {
  await assert.rejects(requestJson("", "/cart", {}, async () => new Response("offline", { status: 503 })), /503/);
});

test("successful malformed JSON is reported instead of returning null", async () => {
  await assert.rejects(requestJson("", "/products", {}, async () => new Response("<html>proxy error</html>")), /JSON/);
});

test("authentication failures retain status and message", async () => {
  await assert.rejects(requestJson("", "/auth/me", {}, async () => new Response(
    JSON.stringify({ detail: "Session expired" }), { status: 401 }
  )), error => error.status === 401 && error.message === "Session expired");
});

test("empty validation details still report HTTP status", async () => {
  await assert.rejects(requestJson("", "/orders", {}, async () => new Response(
    JSON.stringify({ detail: [] }), { status: 422 }
  )), /422/);
});
