const historyBody = document.getElementById("history-body");
const notice = document.getElementById("notice");
const uploadForm = document.getElementById("upload-form");
const uploadButton = document.getElementById("upload-button");
const fileInput = document.getElementById("image");
const drop = document.getElementById("drop");
const followButton = document.getElementById("follow-latest");

let historyCache = [...historyBody.querySelectorAll("tr[data-id]")].map((row) => ({
  id: Number(row.dataset.id),
  captured_date: row.children[1].textContent,
  captured_time: row.children[2].textContent,
  status: row.children[3].textContent,
  region_count: Number(row.children[4].textContent),
}));
let selectedId = Number(historyBody.querySelector("tr.selected")?.dataset.id || 0) || null;
let shownId = selectedId;
let followLive = true;
let busy = false;
const processingTimes = {};

function tickClock() {
  document.getElementById("clock").textContent = new Date().toLocaleString();
}

function setBusy(state) {
  busy = state;
  uploadButton.disabled = state;
  uploadButton.textContent = state ? "Processing…" : "Process image";
  document.querySelectorAll("[data-sample]").forEach((button) => {
    button.disabled = state;
  });
}

function showNotice(message) {
  notice.hidden = !message;
  notice.textContent = message || "";
}

function setFrame(frameId, imageId, url) {
  const frame = document.getElementById(frameId);
  const image = document.getElementById(imageId);
  const placeholder = frame.querySelector(".placeholder");
  image.onload = () => {
    image.hidden = false;
    placeholder.hidden = true;
  };
  image.onerror = () => {
    image.hidden = true;
    placeholder.hidden = false;
    placeholder.textContent = "Image unavailable";
  };
  placeholder.hidden = false;
  placeholder.textContent = "Loading…";
  image.src = url;
}

function renderResult(record) {
  selectedId = record.id;
  const panel = document.getElementById("result-panel");
  const alert = record.region_count > 0;
  panel.classList.toggle("is-alert", alert);
  panel.classList.toggle("is-clear", !alert);
  document.getElementById("status-text").textContent = record.status;
  document.getElementById("region-count").textContent = String(record.region_count);
  document.getElementById("captured-date").textContent = record.captured_date;
  document.getElementById("captured-time").textContent = record.captured_time;

  const timing = document.getElementById("processing-ms");
  timing.textContent = processingTimes[record.id] != null
    ? `${processingTimes[record.id]} ms`
    : "—";

  if (shownId !== record.id) {
    shownId = record.id;
    const stamp = Date.now();
    setFrame("original-frame", "original", `/image/${record.id}?type=original&t=${stamp}`);
    setFrame("processed-frame", "processed", `/image/${record.id}?type=processed&t=${stamp}`);
    setFrame("result-frame", "result", `/image/${record.id}?type=result&t=${stamp}`);
  }
  highlightSelection();
  followButton.hidden = followLive;
}

function renderHistory(rows) {
  if (!rows.length) {
    historyBody.innerHTML = '<tr class="empty"><td colspan="5">No inspection records yet.</td></tr>';
    return;
  }
  historyBody.innerHTML = rows
    .map(
      (row) => `
        <tr data-id="${row.id}" tabindex="0">
          <td>${row.id}</td>
          <td>${row.captured_date}</td>
          <td>${row.captured_time}</td>
          <td>${escapeHtml(row.status)}</td>
          <td>${row.region_count}</td>
        </tr>`
    )
    .join("");
  highlightSelection();
}

function highlightSelection() {
  historyBody.querySelectorAll("tr[data-id]").forEach((row) => {
    row.classList.toggle("selected", Number(row.dataset.id) === selectedId);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function refresh() {
  const response = await fetch("/history");
  if (!response.ok) {
    throw new Error("Could not load inspection history");
  }
  const rows = await response.json();
  const changed = rows.length !== historyCache.length || rows.some((row, index) => {
    const current = historyCache[index];
    return !current || current.id !== row.id || current.region_count !== row.region_count;
  });
  rows.forEach((row) => {
    if (row.processing_ms != null) {
      processingTimes[row.id] = row.processing_ms;
    }
  });
  historyCache = rows;
  if (changed) {
    renderHistory(historyCache);
  }
  if (!historyCache.length) {
    return;
  }
  const chosen = followLive
    ? historyCache[0]
    : historyCache.find((row) => row.id === selectedId) || historyCache[0];
  renderResult(chosen);
}

async function uploadFile(file) {
  showNotice("");
  setBusy(true);
  try {
    const body = new FormData();
    body.append("image", file, file.name || "capture.jpg");
    const response = await fetch("/upload", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Upload failed");
    }
    processingTimes[payload.id] = payload.processing_ms;
    followLive = true;
    selectedId = payload.id;
    await refresh();
  } catch (error) {
    showNotice(error.message);
  } finally {
    setBusy(false);
  }
}

async function uploadSample(name) {
  if (busy) {
    return;
  }
  setBusy(true);
  try {
    const response = await fetch(`/static/samples/${name}`);
    if (!response.ok) {
      throw new Error("Sample image is not available");
    }
    const blob = await response.blob();
    await uploadFile(new File([blob], name, { type: blob.type || "image/jpeg" }));
  } catch (error) {
    showNotice(error.message);
    setBusy(false);
  }
}

uploadForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    showNotice("Choose an image first, or use one of the demonstration samples.");
    return;
  }
  uploadFile(file);
});

drop.addEventListener("dragover", (event) => {
  event.preventDefault();
  drop.classList.add("drag");
});

drop.addEventListener("dragleave", () => drop.classList.remove("drag"));

drop.addEventListener("drop", (event) => {
  event.preventDefault();
  drop.classList.remove("drag");
  const file = event.dataTransfer.files[0];
  if (file) {
    uploadFile(file);
  }
});

document.querySelectorAll("[data-sample]").forEach((button) => {
  button.addEventListener("click", () => {
    uploadSample(button.dataset.sample).catch((error) => showNotice(error.message));
  });
});

followButton.addEventListener("click", () => {
  followLive = true;
  followButton.hidden = true;
  if (historyCache[0]) {
    renderResult(historyCache[0]);
  }
});

historyBody.addEventListener("click", (event) => selectRow(event.target.closest("tr[data-id]")));
historyBody.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }
  const row = event.target.closest("tr[data-id]");
  if (!row) {
    return;
  }
  event.preventDefault();
  selectRow(row);
});

function selectRow(row) {
  if (!row) {
    return;
  }
  followLive = false;
  const record = historyCache.find((item) => item.id === Number(row.dataset.id));
  if (record) {
    renderResult(record);
  }
}

tickClock();
setInterval(tickClock, 1000);
refresh().catch((error) => showNotice(error.message));
setInterval(() => {
  if (!busy) {
    refresh().catch(() => {});
  }
}, 4000);