(async () => {
  const health = document.querySelector("#health");
  const msg = document.querySelector("#message");

  async function refresh() {
    const [state, host] = await Promise.all([
      chrome.runtime.sendMessage({ type: "GET_STATE", keys: ["bookmarks", "gatingDb", "history"] }),
      chrome.runtime.sendMessage({ type: "BRIDGE_HEALTH" })
    ]);
    document.querySelector("#bookmarks").textContent = Object.keys(state?.state?.bookmarks || {}).length;
    document.querySelector("#gates").textContent = Object.keys(state?.state?.gatingDb || {}).length;
    document.querySelector("#history").textContent = (state?.state?.history || []).length;
    health.textContent = host?.ok
      ? `Native host ready · ${host.health?.marketplaceId || "configured"}`
      : `Native host unavailable · ${host?.error || "check Gate Keepa setup"}`;
  }

  document.querySelector("#clear-cache").addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ type: "CLEAR_ELIGIBILITY_CACHE" });
    msg.textContent = "Eligibility cache cleared.";
  });

  document.querySelector("#options").addEventListener("click", () => chrome.runtime.openOptionsPage());

  refresh();
})();
