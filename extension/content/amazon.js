(async () => {
  const SC = globalThis.SourcingCockpit;
  if (!SC) return;

  const asin = SC.asinFromUrl(location.href) || SC.normalizeAsin(document.querySelector("[data-asin]")?.getAttribute("data-asin"));
  if (!asin) return;

  const marketplaceId = SC.marketplaceFromHostname(location.hostname);
  const marketplace = SC.marketplaceInfo(marketplaceId);
  const title =
    document.querySelector("#productTitle")?.textContent?.trim() ||
    document.querySelector("h1")?.textContent?.trim() ||
    document.title;

  const panel = document.createElement("section");
  panel.id = "sc-amazon-panel";
  panel.innerHTML = `
    <div class="sc-panel-title">Gate Keepa · ${asin}</div>
    <div class="sc-line"><span class="sc-badge" data-status="UNKNOWN" id="sc-amz-status">checking…</span></div>
    <div class="sc-line">
      <button class="sc-mini" id="sc-amz-keepa">Open Keepa</button>
      <button class="sc-mini" id="sc-amz-bookmark">☆ Watch</button>
    </div>
    <div class="sc-line" style="display:block">
      <label for="sc-note">Notes</label>
      <textarea id="sc-note" placeholder="Local note for this ASIN"></textarea>
    </div>
  `;
  document.documentElement.appendChild(panel);

  panel.querySelector("#sc-amz-keepa").addEventListener("click", () => {
    window.open(`https://keepa.com/#!product/${marketplace.keepaDomain}-${asin}`, "_blank", "noopener");
  });

  const state = await chrome.runtime.sendMessage({ type: "GET_STATE", keys: ["bookmarks", "notes"] });
  const bookmarks = state?.state?.bookmarks || {};
  const notes = state?.state?.notes || {};
  const bookmarkButton = panel.querySelector("#sc-amz-bookmark");
  bookmarkButton.textContent = bookmarks[asin] ? "★ Watched" : "☆ Watch";
  panel.querySelector("#sc-note").value = notes[asin]?.text || "";

  bookmarkButton.addEventListener("click", async () => {
    const latest = await chrome.runtime.sendMessage({ type: "GET_STATE", keys: ["bookmarks"] });
    const map = latest?.state?.bookmarks || {};
    if (map[asin]) {
      delete map[asin];
      bookmarkButton.textContent = "☆ Watch";
    } else {
      map[asin] = { asin, title, url: location.href, marketplaceId, savedAt: Date.now() };
      bookmarkButton.textContent = "★ Watched";
    }
    await chrome.runtime.sendMessage({ type: "SET_STATE", state: { bookmarks: map } });
  });

  let noteTimer;
  panel.querySelector("#sc-note").addEventListener("input", e => {
    clearTimeout(noteTimer);
    noteTimer = setTimeout(async () => {
      const latest = await chrome.runtime.sendMessage({ type: "GET_STATE", keys: ["notes"] });
      const map = latest?.state?.notes || {};
      map[asin] = { text: e.target.value, updatedAt: Date.now(), title, marketplaceId };
      await chrome.runtime.sendMessage({ type: "SET_STATE", state: { notes: map } });
    }, 350);
  });

  const status = panel.querySelector("#sc-amz-status");
  try {
    const response = await chrome.runtime.sendMessage({ type: "CHECK_ELIGIBILITY", asin, marketplaceId });
    if (!response?.ok) throw new Error(response?.error || "Eligibility failed");
    const result = response.result;
    status.dataset.status = result.status || "UNKNOWN";
    status.textContent =
      result.status === "SELLABLE" ? "● sellable" :
      result.status === "APPROVAL_REQUIRED" ? "● approval required" :
      result.status === "RESTRICTED" ? "● restricted" :
      "● unknown";
    status.title = [result.message, ...(result.reasonCodes || [])].filter(Boolean).join("\n");
    if (result.approvalUrl) {
      status.style.cursor = "pointer";
      status.addEventListener("click", () => window.open(result.approvalUrl, "_blank", "noopener"));
    }
  } catch (error) {
    status.dataset.status = "ERROR";
    status.textContent = "● bridge?";
    status.title = String(error?.message || error);
  }
})();
