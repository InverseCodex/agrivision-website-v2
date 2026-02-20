// ===============================
// index.js (copy-paste ready)
// Works with your current index.html
// Requires static/map.js providing:
//   window.initMissionMap()
//   window.fixMissionMapSize()
// ===============================

// ---- Navbar buttons ----
const navbarButtonInactive = document.querySelectorAll(".navbar-button");
let navbarButtonActive = document.querySelector(".navbar-button-active");

// ---- Layout controls ----
const hamburgerButton = document.querySelector(".hamburger-button");
const hamburgerContainer = document.querySelector(".content-container");
const navbarContainer = document.querySelector(".navbar-container");
const contentContainer = document.querySelector(".content-boxes-container");

// ---- Current active content ----
let activeContent = document.querySelector(".active-content");

// ---- Button IDs ----
const buttonDrone = document.querySelector("#drone-button");
const buttonMission = document.querySelector("#mission-button");
const buttonAnalysis = document.querySelector("#analysis-button");
const buttonHistory = document.querySelector("#history-button");

// ---- Content IDs ----
const contentDrone = document.querySelector("#drone-content");
const contentMission = document.querySelector("#mission-content");
const contentAnalysis = document.querySelector("#analysis-content");
const contentHistory = document.querySelector("#history-content");

// Prevent anchor default
[buttonDrone, buttonMission, buttonAnalysis, buttonHistory].forEach(preventAnchorDefault);

function preventAnchorDefault(el) {
  if (!el) return;
  el.addEventListener("click", (e) => e.preventDefault());
}

// Pair map: button -> content
const buttonContentPair = {
  "drone-button": contentDrone,
  "mission-button": contentMission,
  "analysis-button": contentAnalysis,
  "history-button": contentHistory,
};

const buttonID = [buttonDrone, buttonMission, buttonAnalysis, buttonHistory].filter(Boolean);

// -------------------------------
// Navbar active styling
// -------------------------------
navbarButtonInactive.forEach((button) => {
  button.addEventListener("click", () => {
    if (navbarButtonActive) navbarButtonActive.classList.remove("navbar-button-active");
    button.classList.add("navbar-button-active");
    navbarButtonActive = button;
  });
});

// -------------------------------
// Hamburger toggle
// -------------------------------
if (hamburgerButton) {
  hamburgerButton.addEventListener("click", () => {
    if (navbarContainer) navbarContainer.classList.toggle("navbar-container-inactive");
    if (hamburgerContainer) hamburgerContainer.classList.toggle("inactive-navbar");
    if (contentContainer) contentContainer.classList.toggle("navbar-display");

    // If mission map is visible when toggling, reflow it
    if (activeContent && activeContent.id === "mission-content") {
      if (window.fixMissionMapSize) window.fixMissionMapSize();
    }
  });
}

// -------------------------------
// Tab switching + History load + Mission map fix
// -------------------------------
buttonID.forEach((button) => {
  button.addEventListener("click", () => {
    const next = buttonContentPair[button.id];
    if (!next) return;

    if (activeContent) activeContent.classList.remove("active-content");
    next.classList.add("active-content");
    activeContent = next;

    // History tab: load gallery
    if (button.id === "history-button") {
      loadHistoryGallery();
    }

    // Mission tab: init map once + fix size every time
    if (button.id === "mission-button") {
      if (window.initMissionMap) window.initMissionMap();
      if (window.fixMissionMapSize) window.fixMissionMapSize();
    }
  });
});

// -------------------------------
// Analysis helpers
// -------------------------------
function setAnalysisVisible(hasResult) {
  // analysis-content has two blocks with class .analysis-content
  const analysisBlocks = contentAnalysis ? contentAnalysis.querySelectorAll(".analysis-content") : [];
  let emptyBlock = null;
  let loadedBlock = null;

  analysisBlocks.forEach((b) => {
    if (b.querySelector(".text-no-results")) emptyBlock = b;
    else loadedBlock = b;
  });

  if (!emptyBlock || !loadedBlock) return;

  if (hasResult) {
    emptyBlock.classList.add("inactive");
    loadedBlock.classList.remove("inactive");
  } else {
    emptyBlock.classList.remove("inactive");
    loadedBlock.classList.add("inactive");
  }
}

function setHealthUI(score) {
  const s = Math.max(0, Math.min(100, Number(score) || 0));

  const scoreEl = document.getElementById("analysis-health-number");
  if (scoreEl) scoreEl.textContent = s;

  const bar = document.querySelector(".analysis-health-progress");
  if (bar) bar.style.width = `${s}%`;
}

// -------------------------------
// History gallery
// -------------------------------
async function loadHistoryGallery() {
  const container = document.getElementById("history-gallery");
  if (!container) return;

  container.innerHTML = "<p>Loading...</p>";

  const res = await fetch("/history/images");
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    console.error(data);
    container.innerHTML = "<p>Failed to load history.</p>";
    return;
  }

  if (!data.images || data.images.length === 0) {
    container.innerHTML = "<p>No history yet.</p>";
    return;
  }

  container.innerHTML = "";

  data.images.forEach((img) => {
    const ts = img.uploaded_at ? new Date(img.uploaded_at).toLocaleString() : "Unknown time";

    const card = document.createElement("div");
    card.className = "history-card";
    card.dataset.imageId = img.id;

    card.innerHTML = `
      <div class="history-card-top">
        <div class="history-meta">
          <p class="history-filename">${img.filename ?? "Image"}</p>
          <p class="history-time">${ts}</p>
        </div>
        <button class="history-load-btn" data-image-id="${img.id}">LOAD</button>
      </div>
      <div class="history-thumb">
        <img src="${img.url}" loading="lazy" alt="">
      </div>
    `;

    container.appendChild(card);
  });

  // Event delegation once
  if (!container.dataset.bound) {
    container.addEventListener("click", (e) => {
      const btn = e.target.closest(".history-load-btn");
      if (btn) {
        runAnalysisAndShow(btn.dataset.imageId);
        return;
      }

      const card = e.target.closest(".history-card");
      if (card && card.dataset.imageId) {
        runAnalysisAndShow(card.dataset.imageId);
      }
    });

    container.dataset.bound = "1";
  }
}

// -------------------------------
// Run analysis + update UI
// -------------------------------
async function runAnalysisAndShow(imageId) {
  try {
    const res = await fetch("/analysis/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_id: imageId }),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      console.error(data);
      alert(data.error || "Analysis failed");
      return;
    }

    // Switch active navbar button to Analysis
    if (navbarButtonActive) navbarButtonActive.classList.remove("navbar-button-active");
    if (buttonAnalysis) buttonAnalysis.classList.add("navbar-button-active");
    navbarButtonActive = buttonAnalysis;

    // Switch content to Analysis
    if (activeContent) activeContent.classList.remove("active-content");
    if (contentAnalysis) contentAnalysis.classList.add("active-content");
    activeContent = contentAnalysis;

    // Show real analysis content
    setAnalysisVisible(true);

    // Put images into holders
    const originalHolder = document.getElementById("original-image");
    const aiHolder = document.getElementById("ai-view");

    if (originalHolder) {
      originalHolder.innerHTML = `<img src="${data.original_url}" style="width:100%;height:100%;object-fit:cover;border-radius:1rem;">`;
    }
    if (aiHolder) {
      aiHolder.innerHTML = `<img src="${data.result_url}" style="width:100%;height:100%;object-fit:cover;border-radius:1rem;">`;
    }

    // Health score
    const score = data.metrics?.health_score ?? 0;
    setHealthUI(score);

    // Default to original
    showOriginal();
  } catch (err) {
    console.error(err);
    alert("Error running analysis.");
  }
}

// -------------------------------
// Toggle Original vs AI view
// -------------------------------
const toggleBtn = document.querySelector(".image-header-toggle-button");
const toggleCont = document.querySelector(".image-header-toggle-container");
const circlePointer = document.querySelector(".circle-toggle");

function showOriginal() {
  const originalHolder = document.getElementById("original-image");
  const aiHolder = document.getElementById("ai-view");
  if (originalHolder) originalHolder.style.display = "block";
  if (aiHolder) aiHolder.style.display = "none";
}

function showAI() {
  const originalHolder = document.getElementById("original-image");
  const aiHolder = document.getElementById("ai-view");
  if (originalHolder) originalHolder.style.display = "none";
  if (aiHolder) aiHolder.style.display = "block";
}

if (toggleBtn && circlePointer) {
  toggleBtn.addEventListener("click", () => {
    circlePointer.classList.toggle("inactive-circle");
    if (toggleCont) toggleCont.classList.toggle("image-toggle-active");

    // If inactive-circle is ON, interpret as AI view (flip if you want)
    const isAI = circlePointer.classList.contains("inactive-circle");
    if (isAI) showAI();
    else showOriginal();
  });
}

// -------------------------------
// Mission upload (SEND JSON)
// -------------------------------
const uploadBtn = document.getElementById("upload-mission-btn");

if (uploadBtn) {
  uploadBtn.addEventListener("click", async () => {
    try {
      const lat = parseFloat(document.getElementById("latitude-value")?.textContent || "NaN");
      const lng = parseFloat(document.getElementById("longitude-value")?.textContent || "NaN");
      const alt = parseFloat(document.getElementById("altitude-value")?.value || "NaN");

      if (!Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(alt)) {
        alert("Pick a location on the map and set altitude first.");
        return;
      }

      const missionObj = {
        target: { lat, lng, alt_m: alt },
      };

      const res = await fetch("/mission/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(missionObj),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        console.error(data);
        alert(data.error || "Mission upload failed");
        return;
      }

      alert("Mission queued!");
      console.log("Mission response:", data);

    } catch (err) {
      console.error(err);
      alert("Error sending mission.");
    }
  });
}

// -------------------------------
// Initial state
// -------------------------------
setAnalysisVisible(false);
showOriginal();

// Optional: if Mission tab is active on load, init map
if (activeContent && activeContent.id === "mission-content") {
  if (window.initMissionMap) window.initMissionMap();
  if (window.fixMissionMapSize) window.fixMissionMapSize();
}
