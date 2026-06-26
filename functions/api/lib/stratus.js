const BUCKET_NAME = process.env.STRATUS_BUCKET || "dossiers";
const TTL = parseInt(process.env.SIGNED_URL_TTL_SECONDS || "3600", 10);

function bucket(app) {
  return app.stratus().bucket(BUCKET_NAME);
}

async function putHtml(app, key, html) {
  const b = bucket(app);
  await b.putObject(key, Buffer.from(html, "utf8"), {
    "Content-Type": "text/html; charset=utf-8",
  });
}

async function getHtml(app, key) {
  const b = bucket(app);
  const obj = await b.getObject(key);
  // v3 SDK returns a Readable stream
  if (obj && typeof obj.on === "function") {
    return await new Promise((resolve, reject) => {
      const chunks = [];
      obj.on("data", (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
      obj.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
      obj.on("error", reject);
    });
  }
  if (typeof obj === "string") return obj;
  if (Buffer.isBuffer(obj)) return obj.toString("utf8");
  if (obj && typeof obj.text === "function") return await obj.text();
  return String(obj);
}

async function getSignedUrl(app, key) {
  const b = bucket(app);
  try {
    // Node v2 SDK signature per Catalyst docs:
    //   bucket.generatePreSignedUrl(key, "GET", { expiryIn: <seconds> })
    // → { signature: "https://…/_signed/…?stsExpiresAfter=…", expiry_in_seconds: "…" }
    // The earlier version used `expiry_in_seconds` (snake_case) as the option key
    // AND read `signed_url`/`url`/`presigned_url` off the response — both were
    // wrong. The option key was silently ignored (so the SDK defaulted to 0 or
    // rejected) and the URL lives under `signature`, not `signed_url`.
    const res = await b.generatePreSignedUrl(key, "GET", {
      expiryIn: TTL,
    });
    if (typeof res === "string") return res;
    return (
      res?.signature ||
      res?.signed_url ||
      res?.url ||
      res?.presigned_url ||
      null
    );
  } catch (err) {
    console.warn("stratus generatePreSignedUrl failed:", err.message);
    return null;
  }
}

// Collect whatever getObject returns (Readable stream | Buffer | string) into a
// Buffer. Shared by getHtml above (conceptually) and the PDF cache below.
async function streamToBuffer(obj) {
  if (obj && typeof obj.on === "function") {
    return await new Promise((resolve, reject) => {
      const chunks = [];
      obj.on("data", (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
      obj.on("end", () => resolve(Buffer.concat(chunks)));
      obj.on("error", reject);
    });
  }
  if (Buffer.isBuffer(obj)) return obj;
  if (typeof obj === "string") return Buffer.from(obj, "utf8");
  if (obj && typeof obj.arrayBuffer === "function")
    return Buffer.from(await obj.arrayBuffer());
  return Buffer.from(String(obj));
}

// Fetch a binary object as a Buffer, or null if it doesn't exist / is
// unreachable. Used to serve a cached PDF without re-rendering.
async function getObjectBuffer(app, key) {
  try {
    const obj = await bucket(app).getObject(key);
    if (obj == null) return null;
    const buf = await streamToBuffer(obj);
    return buf.length > 0 ? buf : null;
  } catch {
    return null;
  }
}

// Store a binary object. Best-effort: never throws into the caller.
async function putBuffer(app, key, buf, contentType) {
  try {
    await bucket(app).putObject(key, buf, { "Content-Type": contentType });
    return true;
  } catch (err) {
    console.warn("stratus putBuffer failed (continuing):", err.message);
    return false;
  }
}

async function deleteObject(app, key) {
  const b = bucket(app);
  try {
    await b.deleteObject(key);
  } catch (err) {
    console.warn("stratus deleteObject failed (continuing):", err.message);
  }
}

module.exports = {
  putHtml,
  getHtml,
  getSignedUrl,
  deleteObject,
  getObjectBuffer,
  putBuffer,
  BUCKET_NAME,
};
