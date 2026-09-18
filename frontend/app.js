// HomeMind — Frontend Dashboard Logic (Phases 8 & 9)

let socket = null;
let autoTickInterval = null;
let isAutoTicking = false;

// Agent Node Coordinates for Communication Matrix SVG (500 x 260)
const AGENT_NODES = {
  HOME_MANAGER: { x: 250, y: 55, label: "Home Manager", color: "#8b5cf6" },
  ENERGY:       { x: 90,  y: 145, label: "Energy",       color: "#f59e0b" },
  COMFORT:      { x: 410, y: 145, label: "Comfort",      color: "#06b6d4" },
  SECURITY:     { x: 150, y: 235, label: "Security",     color: "#f43f5e" },
  RESOURCE:     { x: 350, y: 235, label: "Resource",     color: "#10b981" }
};

document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  fetchInitialData();
});

// WebSocket Initialization with Auto-Reconnect
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    document.getElementById("ws-status").innerHTML = '<span class="conn-dot"></span> Live';
    document.getElementById("ws-status").style.color = "#10b981";
  };

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "INIT") {
        renderOverview(msg.overview);
        renderAgents(msg.agents);
        renderTimeline(msg.timeline);
        renderCommunication(msg.communication);
      } else if (msg.type === "STATE_UPDATE") {
        renderOverview(msg.data);
        refreshAgentsAndTimeline();
      } else if (msg.type === "SCENARIO_EXECUTED") {
        refreshAll();
      }
    } catch (e) {
      console.error("Error parsing WebSocket message:", e);
    }
  };

  socket.onclose = () => {
    document.getElementById("ws-status").innerHTML = '<span class="conn-dot" style="background:#f43f5e"></span> Polling';
    document.getElementById("ws-status").style.color = "#f43f5e";
    // Fallback polling every 3 seconds if disconnected
    setTimeout(initWebSocket, 4000);
  };
}

// REST Fallback / Fetch
async function fetchInitialData() {
  try {
    const [ovRes, agRes, tlRes, cmRes] = await Promise.all([
      fetch("/api/overview"),
      fetch("/api/agents"),
      fetch("/api/timeline"),
      fetch("/api/communication")
    ]);
    if (ovRes.ok) renderOverview(await ovRes.json());
    if (agRes.ok) renderAgents(await agRes.json());
    if (tlRes.ok) renderTimeline((await tlRes.json()).timeline);
    if (cmRes.ok) renderCommunication(await cmRes.json());
  } catch (e) {
    console.error("Failed to fetch initial telemetry:", e);
  }
}

async function refreshAll() {
  await fetchInitialData();
}

async function refreshAgentsAndTimeline() {
  try {
    const [agRes, tlRes, cmRes] = await Promise.all([
      fetch("/api/agents"),
      fetch("/api/timeline"),
      fetch("/api/communication")
    ]);
    if (agRes.ok) renderAgents(await agRes.json());
    if (tlRes.ok) renderTimeline((await tlRes.json()).timeline);
    if (cmRes.ok) renderCommunication(await cmRes.json());
  } catch (e) {
    console.error("Refresh error:", e);
  }
}

// 1. Render Home Overview (Section 9)
function renderOverview(data) {
  if (!data) return;

  // State pill
  const stateVal = document.getElementById("home-state-val");
  const statePill = document.getElementById("home-state-pill");
  stateVal.textContent = data.home_state;
  
  // State styling
  if (data.home_state === "AWAY") {
    statePill.style.borderColor = "rgba(244, 63, 94, 0.4)";
    stateVal.style.color = "#fb7185";
  } else if (data.home_state === "SLEEP") {
    statePill.style.borderColor = "rgba(139, 92, 246, 0.4)";
    stateVal.style.color = "#c4b5fd";
  } else if (data.home_state === "MORNING") {
    statePill.style.borderColor = "rgba(245, 158, 11, 0.4)";
    stateVal.style.color = "#fcd34d";
  } else {
    statePill.style.borderColor = "rgba(16, 185, 129, 0.4)";
    stateVal.style.color = "#6ee7b7";
  }

  // Clock
  document.getElementById("sim-clock").textContent = data.sim_time;

  // Metric Cards
  document.getElementById("val-power").textContent = `${data.energy.instant_power_watts} W`;
  document.getElementById("sub-power").textContent = `Daily: ${data.energy.daily_energy_kwh} kWh ${data.energy.is_peak_pricing ? '• PEAK TARIFF' : '• Normal'}`;
  
  document.getElementById("val-climate").textContent = `${data.environment.avg_temperature} °C`;
  document.getElementById("sub-climate").textContent = `Humidity: ${data.environment.avg_humidity}% | Outdoor: ${data.weather.outdoor_temp}°C`;

  document.getElementById("val-water").textContent = `${data.water.tank_percent}%`;
  document.getElementById("sub-water").textContent = `${data.water.tank_liters} L / ${data.water.tank_capacity} L | Flow: ${data.water.flow_rate_lpm} L/m`;
  if (data.water.leak_detected) {
    document.getElementById("val-water").style.color = "#f43f5e";
  } else {
    document.getElementById("val-water").style.color = "var(--text-primary)";
  }

  document.getElementById("val-security").textContent = data.security.lock_state;
  document.getElementById("sub-security").textContent = `Door: ${data.security.door_state} | Away Mode: ${data.security.away_mode_armed ? 'ARMED' : 'OFF'}`;

  const occCount = data.environment.occupied_count;
  document.getElementById("val-occupancy").textContent = occCount > 0 ? `${occCount} Occupied` : "Vacant (0)";
  document.getElementById("sub-occupancy").textContent = occCount > 0 ? data.environment.occupied_rooms.join(", ") : "No presence detected";

  // Rooms & Devices
  renderRoomsAndDevices(data.rooms, data.devices);
}

// 2. Render 5 Specialized Agents (Section 9)
function renderAgents(agentsPayload) {
  if (!agentsPayload || !agentsPayload.agents) return;
  const container = document.getElementById("agents-container");
  container.innerHTML = "";

  const order = ["HOME_MANAGER", "ENERGY", "COMFORT", "SECURITY", "RESOURCE"];

  order.forEach(typeKey => {
    const ag = agentsPayload.agents[typeKey];
    if (!ag) return;

    const card = document.createElement("div");
    card.className = `agent-card agent-${typeKey}`;

    let alertsHtml = "";
    if (ag.alerts && ag.alerts.length > 0) {
      alertsHtml = `<div class="agent-alerts-box">
        <div class="field-label" style="color:#f43f5e;">Alert Active</div>
        ${ag.alerts.map(a => `<div class="alert-item-mini">[${a.severity}] ${a.title}</div>`).join("")}
      </div>`;
    }

    card.innerHTML = `
      <div class="agent-card-header">
        <div class="agent-title-group">
          <h3>${ag.name}</h3>
          <span class="agent-role">${ag.role}</span>
        </div>
        <span class="agent-status-badge status-${ag.status}">${ag.status}</span>
      </div>

      <div class="agent-field">
        <span class="field-label">Current Task</span>
        <div class="field-content">${ag.current_task || 'Idle'}</div>
      </div>

      <div class="agent-field">
        <span class="field-label">Latest Decision</span>
        <div class="field-content">${ag.latest_decision || ag.important_event || 'No recent decision.'}</div>
      </div>

      ${alertsHtml}
    `;
    container.appendChild(card);
  });
}

// 3. Render Rooms & Device Controls
function renderRoomsAndDevices(rooms, devices) {
  const container = document.getElementById("rooms-container");
  container.innerHTML = "";

  Object.values(rooms).forEach(room => {
    const roomCard = document.createElement("div");
    roomCard.className = `room-card ${room.occupied ? 'occupied' : ''}`;

    // Get devices in this room
    const roomDevs = Object.values(devices).filter(d => d.room_id === room.room_id);

    let devListHtml = "";
    roomDevs.forEach(dev => {
      const isLock = dev.device_type === "SMART_LOCK";
      const isOn = isLock ? (dev.attributes.lock_state === "LOCKED") : (dev.power_state === "ON");
      const btnLabel = isLock ? (isOn ? "LOCKED" : "UNLOCKED") : (isOn ? "ON" : "OFF");
      const toggleAction = isLock ? (isOn ? "UNLOCK" : "LOCK") : (isOn ? "TURN_OFF" : "TURN_ON");

      devListHtml += `
        <div class="device-row">
          <span>${dev.name}</span>
          <button class="dev-switch ${isOn ? 'on' : ''}" onclick="controlDevice('${dev.device_id}', '${toggleAction}')">
            ${btnLabel}
          </button>
        </div>
      `;
    });

    roomCard.innerHTML = `
      <div class="room-title-bar">
        <h4>${room.name}</h4>
        <span class="room-occ-badge">${room.occupied ? 'Occupied' : 'Empty'}</span>
      </div>
      <div class="room-stats">
        <span>${room.temperature}°C</span>
        <span>${room.humidity}% RH</span>
        <span>Motion: ${room.motion ? 'YES' : 'NO'}</span>
      </div>
      <div class="room-devices-list">
        ${devListHtml}
      </div>
    `;
    container.appendChild(roomCard);
  });
}

// 4. Render Inter-Agent Communication Matrix (Section 11)
function renderCommunication(data) {
  if (!data) return;

  const badge = document.getElementById("msg-count-badge");
  if (data.recent_messages) {
    badge.textContent = `${data.recent_messages.length} Recent Messages`;
  }

  // Render SVG Graph Topology
  const svg = document.getElementById("comm-graph-svg");
  svg.innerHTML = "";

  // Draw Edges from Matrix
  if (data.matrix && data.matrix.edges) {
    data.matrix.edges.forEach(edge => {
      const srcNode = AGENT_NODES[edge.source];
      const tgtNode = AGENT_NODES[edge.target];
      if (!srcNode || !tgtNode) return;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "line");
      path.setAttribute("x1", srcNode.x);
      path.setAttribute("y1", srcNode.y);
      path.setAttribute("x2", tgtNode.x);
      path.setAttribute("y2", tgtNode.y);
      path.setAttribute("stroke", "rgba(255, 255, 255, 0.2)");
      path.setAttribute("stroke-width", Math.min(4, Math.max(1.5, edge.count * 0.8)));
      path.setAttribute("stroke-dasharray", "4,3");
      svg.appendChild(path);

      // Edge Count Label
      const midX = (srcNode.x + tgtNode.x) / 2;
      const midY = (srcNode.y + tgtNode.y) / 2;
      const countBg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      countBg.setAttribute("cx", midX);
      countBg.setAttribute("cy", midY);
      countBg.setAttribute("r", 9);
      countBg.setAttribute("fill", "#1e293b");
      countBg.setAttribute("stroke", "rgba(255, 255, 255, 0.15)");
      svg.appendChild(countBg);

      const countText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      countText.setAttribute("x", midX);
      countText.setAttribute("y", midY + 3.5);
      countText.setAttribute("text-anchor", "middle");
      countText.setAttribute("font-size", "9px");
      countText.setAttribute("fill", "#94a3b8");
      countText.textContent = edge.count;
      svg.appendChild(countText);
    });
  }

  // Draw Agent Nodes
  Object.keys(AGENT_NODES).forEach(nodeKey => {
    const node = AGENT_NODES[nodeKey];

    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");

    // Glow ring
    const circleRing = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circleRing.setAttribute("cx", node.x);
    circleRing.setAttribute("cy", node.y);
    circleRing.setAttribute("r", 20);
    circleRing.setAttribute("fill", `${node.color}22`);
    circleRing.setAttribute("stroke", node.color);
    circleRing.setAttribute("stroke-width", "2");

    // Inner node
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", 14);
    circle.setAttribute("fill", node.color);

    // Label
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", node.x);
    text.setAttribute("y", node.y + 32);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("font-size", "11px");
    text.setAttribute("font-weight", "600");
    text.setAttribute("fill", "#f1f5f9");
    text.textContent = node.label;

    group.appendChild(circleRing);
    group.appendChild(circle);
    group.appendChild(text);
    svg.appendChild(group);
  });

  // Render Recent Message Bus List
  const stream = document.getElementById("comm-history-list");
  if (data.recent_messages && data.recent_messages.length > 0) {
    stream.innerHTML = "";
    data.recent_messages.forEach(m => {
      const item = document.createElement("div");
      item.className = "msg-item";
      item.innerHTML = `
        <span class="msg-actors">${m.sender} &rarr; ${m.receiver}</span>
        <span class="msg-content">[${m.topic}] ${m.content}</span>
      `;
      stream.appendChild(item);
    });
  }
}

// 5. Render Timeline (Section 10)
function renderTimeline(timelineItems) {
  if (!timelineItems) return;
  const container = document.getElementById("timeline-list");
  const badge = document.getElementById("timeline-count-badge");
  badge.textContent = `${timelineItems.length} Events`;

  container.innerHTML = "";
  timelineItems.forEach(item => {
    const el = document.createElement("div");
    el.className = `timeline-item type-${item.type || 'ACTION'}`;

    let evHtml = "";
    if (item.evidence && item.evidence.length > 0) {
      evHtml = `<div class="tl-evidence">&bull; Evidence: ${item.evidence.join('; ')}</div>`;
    }

    el.innerHTML = `
      <div class="tl-time">${item.time}</div>
      <div class="tl-body">
        <div class="tl-author">${item.source}</div>
        <div class="tl-event">${item.event}</div>
        ${evHtml}
      </div>
    `;
    container.appendChild(el);
  });
}

// 6. Natural Language Chat Handling (Section 12)
async function handleChatSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("chat-input");
  const prompt = input.value.trim();
  if (!prompt) return;

  input.value = "";
  appendChatBubble("user", "You", prompt);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: prompt })
    });
    if (res.ok) {
      const data = await res.json();
      appendChatBubble("bot", "Home Manager", formatBotResponse(data.response));
      refreshAll();
    } else {
      appendChatBubble("bot", "Home Manager", "Error processing instruction.");
    }
  } catch (e) {
    appendChatBubble("bot", "Home Manager", "Network error communicating with coordinator.");
  }
}

function sendPrompt(text) {
  document.getElementById("chat-input").value = text;
  document.getElementById("chat-form").dispatchEvent(new Event("submit"));
}

function appendChatBubble(type, author, content) {
  const box = document.getElementById("chat-messages");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${type}-bubble`;
  bubble.innerHTML = `
    <div class="bubble-author">${author}</div>
    <div>${content}</div>
  `;
  box.appendChild(bubble);
  box.scrollTop = box.scrollHeight;
}

function formatBotResponse(raw) {
  if (!raw) return "";
  // Simple markdown to HTML formatter for bold and lists
  return raw
    .replace(/### (.*)/g, '<h4 style="color:#c4b5fd;margin-bottom:4px;">$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/- (.*)/g, '<div style="margin-left:8px;">&bull; $1</div>')
    .replace(/\n/g, '<br/>');
}

// 7. Device Controls
async function controlDevice(deviceId, action) {
  try {
    await fetch("/api/simulation/device", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId, action: action })
    });
    refreshAll();
  } catch (e) {
    console.error("Device control failed:", e);
  }
}

// 8. Simulation Clock Controls
async function tickSimulation(seconds) {
  try {
    const res = await fetch("/api/simulation/tick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delta_seconds: seconds })
    });
    if (res.ok) {
      renderOverview(await res.json());
      refreshAgentsAndTimeline();
    }
  } catch (e) {
    console.error("Tick failed:", e);
  }
}

function toggleAutoTick() {
  const btn = document.getElementById("auto-tick-btn");
  isAutoTicking = !isAutoTicking;
  if (isAutoTicking) {
    btn.textContent = "Pause";
    btn.classList.add("active");
    autoTickInterval = setInterval(() => tickSimulation(60), 2000);
  } else {
    btn.textContent = "Play";
    btn.classList.remove("active");
    clearInterval(autoTickInterval);
  }
}

// 9. Demonstration Scenarios (Section 8)
async function triggerScenario(id) {
  try {
    const res = await fetch(`/api/scenario/${id}`, { method: "POST" });
    if (res.ok) {
      const report = await res.json();
      openScenarioModal(report);
      refreshAll();
    }
  } catch (e) {
    console.error("Scenario trigger failed:", e);
  }
}

function openScenarioModal(report) {
  document.getElementById("modal-title").textContent = report.title;
  document.getElementById("modal-desc").textContent = report.description;
  document.getElementById("modal-init-state").textContent = report.initial_state;
  document.getElementById("modal-final-state").textContent = report.final_state;
  document.getElementById("modal-explain").textContent = report.explainability_summary;

  const stepsList = document.getElementById("modal-steps");
  stepsList.innerHTML = "";

  report.steps.forEach(st => {
    const card = document.createElement("div");
    card.className = "modal-step-card";
    card.innerHTML = `
      <div class="modal-step-head">
        <span>[Step ${st.step_index}] ${st.time_str} &bull; ${st.actor}</span>
        <span>[${st.action_type}]</span>
      </div>
      <div>${st.description}</div>
      ${st.evidence && st.evidence.length > 0 ? `<div style="font-size:0.72rem;color:#94a3b8;margin-top:3px;">Evidence: ${st.evidence.join('; ')}</div>` : ''}
    `;
    stepsList.appendChild(card);
  });

  document.getElementById("scenario-modal").classList.add("active");
}

function closeScenarioModal() {
  document.getElementById("scenario-modal").classList.remove("active");
}

// Close modal on backdrop click or Escape key
document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("scenario-modal");
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeScenarioModal();
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeScenarioModal();
  });
});

