/**
 * ScreenSense  |  app.js  (updated)
 *
 * Changes:
 *  - Removed Weekly nav/page logic
 *  - ML Insights: only KNN classification + K-Means clustering
 *  - Dashboard: removed pie chart, heatmap smaller with coolwarm palette
 *  - Demo: modal to select from pre-loaded Digital Wellbeing screenshots
 */

const API = "";   // same origin — FastAPI serves the frontend

let state = { raw: null, prediction: null };
let charts = {};

// ═══════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════
function navigate(name) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById(`page-${name}`).classList.add("active");
  document.querySelectorAll(".nav-item").forEach(n => {
    if (n.dataset.page === name) n.classList.add("active");
  });
  if (name === "ml" && state.prediction) buildMLCharts();
}

document.querySelectorAll(".nav-item").forEach(el => {
  el.addEventListener("click", () => navigate(el.dataset.page));
});

// ═══════════════════════════════════════════
// BACKEND HEALTH CHECK
// ═══════════════════════════════════════════
async function checkBackend() {
  const el = document.getElementById("apiStatus");
  const txt = document.getElementById("apiStatusText");
  try {
    const r = await fetch(`${API}/health`);
    if (r.ok) {
      el.className = "api-status ok";
      txt.textContent = "✅ Python backend connected — API key is safe on the server";
    } else throw new Error();
  } catch {
    el.className = "api-status err";
    txt.innerHTML = "⚠️ Backend not running — <code>cd backend && uvicorn app:app --reload</code>";
  }
}
checkBackend();

// ═══════════════════════════════════════════
// FILE HANDLING
// ═══════════════════════════════════════════
function handleDrop(e) {
  e.preventDefault();
  document.getElementById("dropZone").classList.remove("dragging");
  const file = Array.from(e.dataTransfer.files).find(f => f.type.startsWith("image/"));
  if (file) processImage(file);
  else showToast("⚠️ Please drop an image file");
}

function handleFileInput(e) {
  const file = e.target.files[0];
  if (file) processImage(file);
}

function handleCsvUpload(e) {
  const file = e.target.files[0];
  if (file) processCsv(file);
}

// ═══════════════════════════════════════════
// IMAGE → BACKEND → PREDICT
// ═══════════════════════════════════════════
async function processImage(file) {
  const strip = document.getElementById("previewStrip");
  strip.innerHTML = "";
  const img = document.createElement("img");
  img.className = "preview-thumb";
  img.src = URL.createObjectURL(file);
  strip.appendChild(img);

  showAnalysisCard();
  setStep("s1", "active");
  setProgress(10, "Uploading to FastAPI…");

  try {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API}/api/analyze-screenshot`, { method: "POST", body: form });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    setStep("s1","done"); setStep("s2","active");
    setProgress(35, "Claude Vision reading the screenshot…");
    await delay(400);

    state.raw = await res.json();

    setStep("s2","done"); setStep("s3","active");
    setProgress(55, "Extracting app data…");
    await delay(300);

    const pred = await fetch(`${API}/api/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.raw),
    });
    setStep("s3","done"); setStep("s4","active");
    setProgress(75, "Running ML classifier…");
    await delay(300);

    state.prediction = await pred.json();

    setStep("s4","done"); setStep("s5","active");
    setProgress(95, "Building dashboard…");
    await delay(300);

    setStep("s5","done");
    setProgress(100, "Done ✓");

    showResultPreview();
    renderAll();
    document.getElementById("alert-badge").style.display = "inline";
    document.getElementById("profile-status").textContent = state.prediction.risk_label;
    showToast("✅ Analysis complete! Opening dashboard…");
    setTimeout(() => navigate("dashboard"), 1200);

  } catch (err) {
    setProgress(100, `❌ Error: ${err.message}`);
    showToast(`⚠️ ${err.message}`);
    console.error(err);
  }
}

// ═══════════════════════════════════════════
// CSV UPLOAD
// ═══════════════════════════════════════════
async function processCsv(file) {
  showToast("📄 Parsing CSV…");
  const form = new FormData();
  form.append("file", file);
  try {
    const res  = await fetch(`${API}/api/upload-csv`, { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail);
    state.raw = await res.json();
    await runPredict();
  } catch (err) {
    showToast(`⚠️ ${err.message}`);
  }
}

// ═══════════════════════════════════════════
// DEMO SCREENSHOT MODAL
// ═══════════════════════════════════════════

// Pre-loaded demo screenshots metadata
const DEMO_SCREENSHOTS = [
  { id: "demo1", path: "/static/demo_screenshots/demo1.jpeg", label: "Fri 20 Mar — 5h 11m", desc: "Webex + Instagram heavy day" },
  { id: "demo2", path: "/static/demo_screenshots/demo2.jpeg", label: "Thu 26 Mar — 6h 35m", desc: "Phone + Instagram + Brave" },
  { id: "demo3", path: "/static/demo_screenshots/demo3.jpeg", label: "Sat 28 Mar — 1h 57m", desc: "Instagram dominant (Today)" },
  { id: "demo4", path: "/static/demo_screenshots/demo4.jpeg", label: "Mon 16 Mar — 4h 12m", desc: "Instagram 3h+ session" },
  { id: "demo5", path: "/static/demo_screenshots/demo5.jpeg", label: "Thu 8 Jan — 8h 12m", desc: "Snapchat + Instagram peak" },
  { id: "demo6", path: "/static/demo_screenshots/demo6.jpeg", label: "Wed 31 Dec — 10h 17m", desc: "High usage day — Zoho + Instagram" },
];

function openDemoModal() {
  const modal = document.getElementById("demoModal");
  const grid  = document.getElementById("demoGrid");

  grid.innerHTML = DEMO_SCREENSHOTS.map(s => `
    <div class="demo-card" onclick="selectDemoScreenshot('${s.path}', '${s.label}')">
      <img src="${s.path}" alt="${s.label}" class="demo-thumb" onerror="this.parentElement.style.display='none'">
      <div class="demo-info">
        <div class="demo-label">${s.label}</div>
        <div class="demo-desc">${s.desc}</div>
      </div>
    </div>`).join("");

  modal.style.display = "flex";
}

function closeDemoModal(e) {
  if (e.target === document.getElementById("demoModal")) closeDemoModalDirect();
}

function closeDemoModalDirect() {
  document.getElementById("demoModal").style.display = "none";
}

async function selectDemoScreenshot(path, label) {
  closeDemoModalDirect();
  showToast(`🎭 Loading demo: ${label}…`);

  // Fetch the image file from static path, then process as uploaded image
  try {
    const response = await fetch(path);
    const blob = await response.blob();
    const filename = path.split("/").pop();
    const file = new File([blob], filename, { type: blob.type || "image/jpeg" });
    processImage(file);
  } catch (err) {
    // Fallback: if static fetch fails (e.g. backend not serving static), load sample data
    showToast("⚠️ Could not load image directly — loading sample data instead");
    loadSampleData();
  }
}

// ═══════════════════════════════════════════
// SAMPLE DATA FALLBACK
// ═══════════════════════════════════════════
async function loadSampleData() {
  showAnalysisCard();
  const steps = ["s1","s2","s3","s4","s5"];
  for (let i = 0; i < steps.length; i++) {
    if (i > 0) setStep(steps[i-1], "done");
    setStep(steps[i], "active");
    setProgress((i+1)/steps.length*100, `Processing step ${i+1}…`);
    await delay(350);
  }
  setStep("s5","done"); setProgress(100,"Done ✓");

  try {
    const res = await fetch(`${API}/api/sample-data`);
    state.raw = await res.json();
    await runPredict();
  } catch (err) {
    showToast(`⚠️ ${err.message}`);
  }
}

async function runPredict() {
  const res = await fetch(`${API}/api/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.raw),
  });
  state.prediction = await res.json();
  showResultPreview();
  renderAll();
  document.getElementById("alert-badge").style.display = "inline";
  document.getElementById("profile-status").textContent = state.prediction.risk_label;
  showToast("✅ Dashboard ready!");
  setTimeout(() => navigate("dashboard"), 1000);
}

// ═══════════════════════════════════════════
// RENDER ALL DASHBOARDS
// ═══════════════════════════════════════════
function renderAll() {
  renderDashboard();
  renderAlerts();
}

// ─── Dashboard ───────────────────────────────
function renderDashboard() {
  const d = state.raw;
  const p = state.prediction;
  const f = p.features;

  // Destroy old charts
  ["topAppsChart","trendChart"].forEach(id => { if(charts[id]){charts[id].destroy();delete charts[id];} });

  // Stories
  const stories = [
    { ring:"warn", icon:"⚠️", label:"Alerts" },
    { ring:"",     icon:"📲", label: d.apps[0]?.name || "Top App" },
    { ring:"gray", icon:"🌙", label:"Night Use" },
    { ring:"",     icon:"🔔", label:"Notifs" },
    { ring:"gray", icon:"🎯", label:"Focus" },
  ];
  document.getElementById("storiesRow").innerHTML = stories.map(s => `
    <div class="story-card">
      <div class="story-ring ${s.ring}"><div class="story-inner-el">${s.icon}</div></div>
      <div class="story-label">${s.label}</div>
    </div>`).join("");

  // KPIs
  setText("kpi-total",    fmtMins(f.total_daily_screen_time));
  setText("kpi-total-ch", f.total_daily_screen_time > 300 ? "▲ Above average" : "✓ Within range");
  document.getElementById("kpi-total-ch").className = "kpi-change " + (f.total_daily_screen_time > 300 ? "up" : "down");
  setText("kpi-top",      fmtMins(f.top_app_minutes));
  setText("kpi-top-name", f.top_app_name);
  setText("kpi-social",   Math.round(f.social_media_ratio * 100) + "%");
  setText("kpi-social-warn", f.social_media_ratio > 0.4 ? "▲ High social ratio" : "✓ Social ratio ok");
  setText("kpi-score",    p.health_score);
  document.getElementById("kpi-score-label").innerHTML = `<span style="color:${cssColor(p.risk_level)}">${p.risk_label}</span>`;
  document.getElementById("dash-date").textContent = d.date;

  // Top apps donut
  charts["topAppsChart"] = new Chart(document.getElementById("topAppsChart"), {
    type:"doughnut",
    data:{ labels:d.apps.map(a=>a.name), datasets:[{data:d.apps.map(a=>a.minutes),backgroundColor:d.apps.map(a=>a.color),borderWidth:3,borderColor:"#fff",hoverOffset:6}] },
    options:{responsive:true,maintainAspectRatio:false,cutout:"60%",plugins:{legend:{display:false},tooltip:{backgroundColor:"#1a1a18",bodyColor:"#fff",callbacks:{label:ctx=>`${ctx.label}: ${fmtMins(ctx.parsed)}`}}}}
  });
  document.getElementById("topAppsLegend").innerHTML = d.apps.map(a=>`<div class="legend-item"><div class="legend-dot" style="background:${a.color}"></div><div class="legend-name">${a.name}</div><div class="legend-val">${fmtMins(a.minutes)}</div></div>`).join("");

  // Score ring
  const circ = 2 * Math.PI * 64;
  const offset = circ - (p.health_score / 100) * circ;
  setText("scoreNumBig", p.health_score);
  const chip = document.getElementById("scoreLabelChip");
  chip.textContent = p.risk_label;
  chip.style.color = cssColor(p.risk_level);
  chip.style.background = bgColor(p.risk_level);
  setTimeout(() => {
    const arc = document.getElementById("scoreArc");
    if (arc) { arc.style.transition = "stroke-dashoffset 1.2s ease"; arc.style.strokeDashoffset = offset; }
  }, 300);

  // Score breakdown
  const topPct = Math.round(f.top_app_ratio * 100);
  const socialPct = Math.round(f.social_media_ratio * 100);
  document.getElementById("scoreBreakdown").innerHTML = `
    ${sbRow("Social ratio",     socialPct, socialPct > 50 ? "var(--danger)" : "var(--warn)")}
    ${sbRow("Top app depend.",  topPct,    topPct    > 60 ? "var(--danger)" : "var(--ok)")}
    ${sbRow("Total screen time",Math.min(100,Math.round(f.total_daily_screen_time/480*100)), f.total_daily_screen_time>360?"var(--danger)":"var(--ok)")}`;

  // Trend chart
  const wdays = d.weekly_data?.length ? d.weekly_data : [{ day:"Today", hours:+(f.total_daily_screen_time/60).toFixed(1) }];
  charts["trendChart"] = new Chart(document.getElementById("trendChart"), {
    type:"bar",
    data:{
      labels: wdays.map(w=>w.day),
      datasets:[{
        label:"Screen Time (h)", data:wdays.map(w=>w.hours),
        backgroundColor:wdays.map(w=>w.hours>6?"rgba(232,74,95,0.8)":w.hours>4?"rgba(245,166,35,0.8)":"rgba(77,208,179,0.7)"),
        borderRadius:8,
      },{
        type:"line",label:"Healthy limit",data:Array(wdays.length).fill(3),
        borderColor:"rgba(77,208,179,0.4)",borderDash:[5,4],borderWidth:1.5,pointRadius:0,fill:false,
      }]
    },
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{labels:{boxWidth:10}},tooltip:{backgroundColor:"#1a1a18",bodyColor:"#fff"}},
      scales:{x:{grid:{display:false}},y:{grid:{color:"#f5f5f3"},title:{display:true,text:"hours"}}}}
  });

  buildHeatmap(f.total_daily_screen_time);
}

function sbRow(label, pct, color) {
  return `<div class="sb-row"><span class="sb-label">${label}</span>
    <div class="sb-right">
      <div class="sb-bar"><div class="sb-fill" style="width:${pct}%;background:${color}"></div></div>
      <span style="font-size:11px;font-weight:700">${pct}%</span>
    </div></div>`;
}

// ─── Heatmap — smaller, coolwarm palette ──────────────────────────────
function buildHeatmap(totalMins) {
  const grid = document.getElementById("heatmapGrid");
  grid.innerHTML = "";
  const dLabels = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  const hLabels = ["12a","6a","12p","6p"];   // fewer rows = smaller
  // Condensed 4-row version (12a, 6a, 12p, 6p)
  const base = [
    [1,0,1,0,1,2,1],   // 12a – low midnight activity
    [3,4,2,4,3,6,3],   // 6a  – morning ramp
    [6,5,4,6,5,8,6],   // 12p – peak midday
    [7,6,8,7,8,9,8],   // 6p  – peak evening
  ];
  const intensity = Math.min(9, Math.round(totalMins / 40));
  base[2][4] = intensity; base[3][4] = Math.min(9, intensity+1);

  // Coolwarm: blue (cool/low) → white (neutral) → red (warm/high)
  const col = v => {
    const t = v / 9;
    if (t < 0.2) return `rgba(49,130,189,${0.3 + t})`;          // blue
    if (t < 0.45) return `rgba(103,169,207,${0.4 + t * 0.5})`;  // light blue
    if (t < 0.55) return `rgba(220,220,220,0.9)`;                // neutral white
    if (t < 0.75) return `rgba(239,138,98,${0.5 + t * 0.4})`;   // orange
    return `rgba(215,48,39,${0.65 + t * 0.35})`;                 // red
  };

  // Header row
  grid.appendChild(document.createElement("div"));
  dLabels.forEach(d => {
    const el = document.createElement("div");
    el.className = "hm-day-label";
    el.textContent = d;
    grid.appendChild(el);
  });

  hLabels.forEach((h, hi) => {
    const lbl = document.createElement("div");
    lbl.className = "hm-label";
    lbl.textContent = h;
    grid.appendChild(lbl);
    base[hi].forEach((v, di) => {
      const cell = document.createElement("div");
      cell.className = "hm-cell";
      cell.style.background = col(v);
      cell.title = `${dLabels[di]} ${h}: level ${v}/9`;
      grid.appendChild(cell);
    });
  });
}

// ─── Alerts ───────────────────────────────────
function renderAlerts() {
  const p = state.prediction;
  document.getElementById("alertCount").textContent = `${p.alerts.length} detected`;
  document.getElementById("alertsList").innerHTML = p.alerts.map((a,i) => `
    <div class="alert-item ${a.level}" style="animation-delay:${i*0.07}s">
      <div class="alert-emoji">${a.emoji}</div>
      <div>
        <div class="alert-title">${a.title}</div>
        <div class="alert-desc">${a.desc}</div>
        <span class="alert-tag tag-${a.level === "high" ? "high" : a.level === "medium" ? "medium" : "low"}">${a.tag}</span>
      </div>
    </div>`).join("");

  document.getElementById("recsList").innerHTML = p.recommendations.map(r => `
    <div class="rec-card">
      <div class="rec-num">${r.num}</div>
      <div>
        <div class="rec-title">${r.title}</div>
        <div class="rec-desc">${r.desc}</div>
        <div class="rec-stars">${r.stars} <span style="font-size:11px;color:var(--gray-400)">${r.impact}</span></div>
      </div>
    </div>`).join("");
}

// ─── ML Charts — KNN Classification + K-Means only ────────────────────
function buildMLCharts() {
  if (!state.prediction) return;
  ["clusterChart"].forEach(id=>{if(charts[id]){charts[id].destroy();delete charts[id];}});
  const p = state.prediction;
  const f = p.features;

  // KNN Classification result
  document.getElementById("mlClassResult").innerHTML = `
    <div class="ml-result-emoji">${p.risk_level==="healthy"?"✅":p.risk_level==="moderate"?"⚠️":"🚨"}</div>
    <div class="ml-result-label" style="color:${cssColor(p.risk_level)}">${p.risk_level.toUpperCase()} RISK</div>
    <div class="ml-result-conf">KNN Confidence: ${Math.round(p.classification_confidence*100)}%</div>`;

  document.getElementById("clusterDesc").innerHTML = `You're in <strong>Cluster ${p.cluster} — ${p.cluster_name}</strong>. Social ratio: ${Math.round(f.social_media_ratio*100)}%, top app: ${f.top_app_name} (${fmtMins(f.top_app_minutes)}).`;

  // K-Means scatter plot
  const mkC = (cx,cy,n) => Array.from({length:n},()=>({x:cx+(Math.random()-.5)*2.8,y:cy+(Math.random()-.5)*2.8}));
  const sh = +(f.social_media_minutes/60).toFixed(1);
  const th = +(f.total_daily_screen_time/60).toFixed(1);
  charts["clusterChart"] = new Chart(document.getElementById("clusterChart"),{
    type:"scatter",
    data:{datasets:[
      {label:"Healthy",   data:mkC(1,2,20), backgroundColor:"rgba(77,208,179,0.6)",  pointRadius:4},
      {label:"Moderate",  data:mkC(3,4.5,20),backgroundColor:"rgba(245,166,35,0.7)",  pointRadius:4},
      {label:"High Risk", data:mkC(5,7,18), backgroundColor:"rgba(232,74,95,0.6)",   pointRadius:4},
      {label:"★ You",     data:[{x:sh,y:th}],backgroundColor:"#dc2743",              pointRadius:11,pointStyle:"star"},
    ]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{boxWidth:10,font:{size:10}}},tooltip:{backgroundColor:"#1a1a18",bodyColor:"#fff"}},
      scales:{x:{grid:{color:"#f5f5f3"},title:{display:true,text:"Social (h)"}},y:{grid:{color:"#f5f5f3"},title:{display:true,text:"Total (h)"}}}}
  });
}

// ═══════════════════════════════════════════
// EXTRACTED RESULT PREVIEW (upload page)
// ═══════════════════════════════════════════
function showResultPreview() {
  const d = state.raw;
  const p = state.prediction;
  const total = p.features.total_daily_screen_time;

  document.getElementById("resDate").textContent = d.date;
  document.getElementById("resTotal").textContent = fmtMins(total);
  document.getElementById("resRisk").innerHTML = `<span class="risk-chip risk-${p.risk_level}">${p.risk_label}</span>`;

  document.getElementById("resAppList").innerHTML = d.apps.map(a => `
    <div class="res-app">
      <div class="res-app-dot" style="background:${a.color}"></div>
      <div class="res-app-name">${a.name}</div>
      <div class="res-app-bar"><div class="res-app-fill" style="width:${Math.round(a.minutes/total*100)}%;background:${a.color}"></div></div>
      <div class="res-app-time">${fmtMins(a.minutes)} (${Math.round(a.minutes/total*100)}%)</div>
    </div>`).join("");

  document.getElementById("resSummary").innerHTML = `🧠 <strong>AI:</strong> Top app is <strong>${p.features.top_app_name}</strong> at <strong>${fmtMins(p.features.top_app_minutes)}</strong> (${Math.round(p.features.top_app_ratio*100)}%). Social media = ${Math.round(p.features.social_media_ratio*100)}%. Health score: <strong>${p.health_score}/100</strong>.`;

  document.getElementById("resultPreview").classList.add("show");
}

// ═══════════════════════════════════════════
// ANALYSIS CARD HELPERS
// ═══════════════════════════════════════════
function showAnalysisCard() {
  const card = document.getElementById("analysisCard");
  card.classList.add("show");
  ["s1","s2","s3","s4","s5"].forEach(id => {
    const el = document.getElementById(id);
    el.classList.remove("active","done");
    el.querySelector(".a-icon").textContent = id.slice(1);
    el.querySelector(".a-icon").style.background = "";
    el.querySelector(".a-icon").style.color = "";
  });
  document.getElementById("progressFill").style.width = "0%";
  document.getElementById("resultPreview").classList.remove("show");
}

function setStep(id, state) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove("active","done");
  el.classList.add(state);
  const icon = el.querySelector(".a-icon");
  if (state === "done")   { icon.textContent = "✓"; icon.style.background = "var(--ok)";   icon.style.color = "white"; }
  if (state === "active") { icon.textContent = id.slice(1); icon.style.background = "var(--coral)"; icon.style.color = "white"; }
}

function setProgress(pct, msg) {
  document.getElementById("progressFill").style.width = pct + "%";
  document.getElementById("statusLine").textContent = msg;
}

// ═══════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════
function fmtMins(m) {
  if (!m) return "0m";
  const h = Math.floor(m / 60), mn = m % 60;
  return h > 0 ? `${h}h ${mn}m` : `${mn}m`;
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function cssColor(level) {
  return level === "healthy" ? "var(--ok)" : level === "moderate" ? "var(--warn)" : "var(--danger)";
}

function bgColor(level) {
  return level === "healthy" ? "rgba(60,183,126,0.12)" : level === "moderate" ? "rgba(245,166,35,0.12)" : "rgba(232,74,95,0.1)";
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 4000);
}

// Chart defaults
Chart.defaults.font.family = "'DM Sans', sans-serif";
Chart.defaults.font.size   = 12;
Chart.defaults.color       = "#a0a09a";
Chart.defaults.borderColor = "#ededea";
