const DEFAULTS = {
  marketplaceId: "ATVPDKIKX0DER",
  conditionType: "used_good",
  cacheTtlHours: 168,
  autoScan: true
};

const NATIVE_HOST = "com.marcmy.gatekeepa";
const inflight = new Map();
let storageMutationQueue = Promise.resolve();
let nativePort = null;
let nativeSequence = 0;
const nativePending = new Map();

function normalizedSettings(stored = {}) {
  return {
    marketplaceId: String(stored.marketplaceId || DEFAULTS.marketplaceId),
    conditionType: String(stored.conditionType ?? DEFAULTS.conditionType),
    cacheTtlHours: Math.max(1, Number(stored.cacheTtlHours) || DEFAULTS.cacheTtlHours),
    autoScan: stored.autoScan === undefined ? DEFAULTS.autoScan : Boolean(stored.autoScan)
  };
}

chrome.runtime.onInstalled.addListener(async () => {
  const stored = await chrome.storage.local.get("settings");
  // Deliberately rewrite only supported keys. This removes legacy localhost
  // bridge tokens/URLs and the old optional Gist token from browser storage.
  await chrome.storage.local.set({ settings: normalizedSettings(stored.settings || {}) });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender)
    .then(sendResponse)
    .catch(error => sendResponse({ ok: false, error: String(error?.message || error) }));
  return true;
});

function serializedStorage(work) {
  const task = storageMutationQueue.then(work, work);
  storageMutationQueue = task.catch(() => undefined);
  return task;
}

async function mutateStorageKey(key, fallback, mutator) {
  return serializedStorage(async () => {
    const currentResult = await chrome.storage.local.get(key);
    const current = currentResult[key] ?? fallback;
    const result = await mutator(current);
    await chrome.storage.local.set({ [key]: current });
    return result;
  });
}

async function getSettings() {
  const { settings = {} } = await chrome.storage.local.get("settings");
  return normalizedSettings(settings);
}

async function setSettings(patch) {
  return serializedStorage(async () => {
    const { settings: stored = {} } = await chrome.storage.local.get("settings");
    const settings = normalizedSettings({ ...stored, ...(patch || {}) });
    await chrome.storage.local.set({ settings });
    return settings;
  });
}

async function storageGet(key, fallback) {
  const result = await chrome.storage.local.get(key);
  return result[key] ?? fallback;
}

async function storageSet(key, value) {
  return serializedStorage(() => chrome.storage.local.set({ [key]: value }));
}

function ensureNativePort() {
  if (nativePort) return nativePort;

  const port = chrome.runtime.connectNative(NATIVE_HOST);
  nativePort = port;

  port.onMessage.addListener(message => {
    const id = message?.id;
    if (!nativePending.has(id)) return;
    const pending = nativePending.get(id);
    nativePending.delete(id);
    clearTimeout(pending.timer);
    pending.resolve(message?.response || { ok: false, error: "Native host returned an empty response" });
  });

  port.onDisconnect.addListener(() => {
    if (nativePort === port) nativePort = null;
    const error = new Error("Gate Keepa native host disconnected. Reinstall or repair Gate Keepa if this persists.");
    for (const pending of nativePending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    nativePending.clear();
  });

  return port;
}

function nativeRequest(request, timeoutMs = 40000) {
  return new Promise((resolve, reject) => {
    const id = `${Date.now().toString(36)}-${(++nativeSequence).toString(36)}`;
    const timer = setTimeout(() => {
      nativePending.delete(id);
      reject(new Error("Gate Keepa native host timed out"));
    }, timeoutMs);

    nativePending.set(id, { resolve, reject, timer });
    try {
      ensureNativePort().postMessage({ id, request });
    } catch (error) {
      clearTimeout(timer);
      nativePending.delete(id);
      nativePort = null;
      reject(error);
    }
  });
}

function cacheKey(asin, marketplaceId, conditionType) {
  return `${marketplaceId}|${conditionType || ""}|${asin}`;
}

async function checkEligibility(asin, force = false, marketplaceOverride = null) {
  const settings = await getSettings();
  const marketplaceId = marketplaceOverride || settings.marketplaceId;
  const key = cacheKey(asin, marketplaceId, settings.conditionType);
  const cache = await storageGet("eligibilityCache", {});
  const now = Date.now();
  const ttlMs = Math.max(1, Number(settings.cacheTtlHours) || 168) * 3600_000;
  const cached = cache[key];

  if (!force && cached && now - cached.cachedAt < ttlMs) {
    return { ...cached, source: "cache" };
  }

  if (inflight.has(key)) return inflight.get(key);

  const promise = (async () => {
    const payload = await nativeRequest({
      type: "eligibility",
      asins: [asin],
      marketplaceIds: [marketplaceId],
      conditionType: settings.conditionType || null
    });

    if (!payload?.ok) {
      throw new Error(payload?.error || "Native host eligibility request failed");
    }

    const item = payload.results?.[asin];
    if (!item) throw new Error(`Native host returned no result for ${asin}`);

    const entry = { ...item, asin, marketplaceId, cachedAt: Date.now(), source: "live" };
    await mutateStorageKey("eligibilityCache", {}, current => {
      current[key] = entry;
    });
    return entry;
  })().finally(() => inflight.delete(key));

  inflight.set(key, promise);
  return promise;
}

async function appendHistory(entry) {
  const normalized = {
    asin: entry.asin,
    title: entry.title || "",
    brand: entry.brand || "",
    category: entry.category || "",
    eligibility: entry.eligibility || "UNKNOWN",
    price: entry.price ?? "",
    sellerCount: entry.sellerCount ?? "",
    score: entry.score ?? "",
    flags: Array.isArray(entry.flags) ? entry.flags.join("|") : (entry.flags || ""),
    url: entry.url || "",
    observedAt: entry.observedAt || Date.now()
  };

  await mutateStorageKey("history", [], history => {
    history.unshift(normalized);
    history.splice(2000);
  });
  return normalized;
}

async function observeSellerCount(asin, sellerCount) {
  if (!Number.isFinite(sellerCount)) return { trend: "unknown", delta: null };

  return mutateStorageKey("sellerObservations", {}, all => {
    const series = all[asin] || [];
    const previous = series.at(-1);
    series.push({ count: sellerCount, at: Date.now() });
    if (series.length > 30) series.splice(0, series.length - 30);
    all[asin] = series;

    if (!previous || !Number.isFinite(previous.count) || previous.count === 0) {
      return { trend: "flat", delta: 0 };
    }
    const delta = (sellerCount - previous.count) / previous.count;
    if (delta >= 0.1) return { trend: "up", delta };
    if (delta <= -0.1) return { trend: "down", delta };
    return { trend: "flat", delta };
  });
}

async function upsertGatingObservation(observation) {
  await mutateStorageKey("gatingDb", {}, db => {
    const keys = [];
    if (observation.brand) keys.push(`brand:${observation.brand.trim().toLowerCase()}`);
    if (observation.category) keys.push(`category:${observation.category.trim().toLowerCase()}`);

    for (const key of keys) {
      const current = db[key] || { counts: {}, lastSeenAt: 0, examples: [] };
      current.counts[observation.eligibility] = (current.counts[observation.eligibility] || 0) + 1;
      current.lastSeenAt = Date.now();
      current.examples = [
        { asin: observation.asin, title: observation.title || "", eligibility: observation.eligibility },
        ...(current.examples || []).filter(x => x.asin !== observation.asin)
      ].slice(0, 10);
      db[key] = current;
    }
  });
}

async function handleMessage(message) {
  switch (message?.type) {
    case "GET_SETTINGS":
      return { ok: true, settings: await getSettings() };

    case "SET_SETTINGS":
      return { ok: true, settings: await setSettings(message.patch || {}) };

    case "CHECK_ELIGIBILITY":
      return {
        ok: true,
        result: await checkEligibility(
          message.asin,
          Boolean(message.force),
          message.marketplaceId || null
        )
      };

    case "CLEAR_ELIGIBILITY_CACHE":
      await storageSet("eligibilityCache", {});
      return { ok: true };

    case "GET_STATE": {
      const keys = Array.isArray(message.keys) ? message.keys : [];
      const state = await chrome.storage.local.get(keys);
      return { ok: true, state };
    }

    case "SET_STATE":
      await serializedStorage(() => chrome.storage.local.set(message.state || {}));
      return { ok: true };

    case "APPEND_HISTORY":
      return { ok: true, entry: await appendHistory(message.entry || {}) };

    case "OBSERVE_SELLERS":
      return { ok: true, ...(await observeSellerCount(message.asin, Number(message.sellerCount))) };

    case "OBSERVE_GATING":
      await upsertGatingObservation(message.observation || {});
      return { ok: true };

    case "BRIDGE_HEALTH": {
      const health = await nativeRequest({ type: "ping" }, 10000);
      return {
        ok: Boolean(health?.ok && health?.configured),
        health,
        transport: "native-messaging",
        error: health?.ok && health?.configured ? "" : (health?.error || "Amazon setup is incomplete")
      };
    }

    default:
      throw new Error(`Unknown message type: ${message?.type}`);
  }
}
