/*
========================================================================
   KRYON Cyber-Operations Platform - Application Controller
========================================================================
*/

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Global Navigation & Sidebar Collapse ---
    const sidebar = document.getElementById('app-sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const toggleChatBtn = document.getElementById('toggle-chat-btn');
    const togglePuppeteerBtn = document.getElementById('toggle-puppeteer-btn');
    const navMode1 = document.getElementById('nav-mode-1');
    const navMode2 = document.getElementById('nav-mode-2');
    const chatWorkspace = document.getElementById('chat-workspace');
    const puppeteerWorkspace = document.getElementById('puppeteer-workspace');
    const modeIndicator = document.getElementById('global-mode-indicator');

    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
        setTimeout(drawTentacles, 360);
    }

    sidebarToggle.addEventListener('click', toggleSidebar);

    function switchMode(mode) {
        if (mode === 'chat') {
            toggleChatBtn.classList.add('active');
            togglePuppeteerBtn.classList.remove('active');
            navMode1.classList.add('active');
            navMode2.classList.remove('active');
            chatWorkspace.classList.add('active');
            puppeteerWorkspace.classList.remove('active');
            modeIndicator.textContent = "MODE 1 // STANDARD CHAT";
        } else {
            toggleChatBtn.classList.remove('active');
            togglePuppeteerBtn.classList.add('active');
            navMode1.classList.remove('active');
            navMode2.classList.add('active');
            chatWorkspace.classList.remove('active');
            puppeteerWorkspace.classList.add('active');
            modeIndicator.textContent = "MODE 2 // PUPPETEERING";
            setTimeout(() => {
                drawTentacles();
                updateOrchestratorLayout();
            }, 50);
        }
    }

    toggleChatBtn.addEventListener('click', () => switchMode('chat'));
    togglePuppeteerBtn.addEventListener('click', () => switchMode('puppeteer'));
    navMode1.addEventListener('click', () => switchMode('chat'));
    navMode2.addEventListener('click', () => switchMode('puppeteer'));

    // --- 2. Draggable Split Panel Resizer ---
    const resizer = document.getElementById('panel-resizer');
    const leftPanel = document.getElementById('orchestrator-split-left');
    const rightPanel = document.getElementById('orchestrator-split-right');
    let isDragging = false;

    resizer.addEventListener('mousedown', (e) => {
        isDragging = true;
        resizer.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const containerWidth = leftPanel.parentElement.clientWidth;
        let leftWidth = e.clientX - leftPanel.parentElement.getBoundingClientRect().left;

        const minWidth = containerWidth * 0.25;
        const maxWidth = containerWidth * 0.75;
        if (leftWidth < minWidth) leftWidth = minWidth;
        if (leftWidth > maxWidth) leftWidth = maxWidth;

        const leftPercent = (leftWidth / containerWidth) * 100;
        const rightPercent = 100 - leftPercent;

        leftPanel.style.flex = leftPercent;
        rightPanel.style.flex = rightPercent;

        drawTentacles();
    });

    document.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            resizer.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            drawTentacles();
        }
    });

    // --- 3. Mode 1: Standard Chat Engine ---
    const chatFeed = document.getElementById('chat-feed');
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');
    const attachBtn = document.getElementById('attach-btn');
    const citationToggleBtn = document.getElementById('citation-toggle-btn');
    const rightSidebar = document.getElementById('chat-right-panel');
    const closeCitations = document.getElementById('close-citations');
    const attachmentPreview = document.getElementById('attachment-preview');
    const attachmentRemoveBtn = document.getElementById('attachment-remove-btn');

    let hasAttachment = false;

    citationToggleBtn.addEventListener('click', () => {
        rightSidebar.classList.toggle('collapsed');
    });
    closeCitations.addEventListener('click', () => {
        rightSidebar.classList.add('collapsed');
    });

    attachBtn.addEventListener('click', () => {
        hasAttachment = true;
        attachmentPreview.style.display = 'flex';
        chatInput.placeholder = "File attached. Ready to upload...";
    });
    attachmentRemoveBtn.addEventListener('click', () => {
        hasAttachment = false;
        attachmentPreview.style.display = 'none';
        chatInput.placeholder = "Type a message or load a playbook (Ctrl + Enter to send)...";
    });

    function appendMessage(sender, text, isUser = false) {
        const wrapper = document.querySelector('.chat-messages .chat-wrapper');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'system'}`;

        let formattedText = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        formattedText = formattedText.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            const cleanCode = code.trim();
            const language = lang ? lang.toUpperCase() : 'CODE';
            return `
                <div class="code-header">
                    <span>${language}</span>
                    <button class="copy-btn" onclick="copyCodeBlock(this)">Copy</button>
                </div>
                <pre><code>${cleanCode}</code></pre>
            `;
        });

        formattedText = formattedText.replace(/`([^`]+)`/g, '<code>$1</code>');

        messageDiv.innerHTML = `
            <div class="avatar" style="background-color: ${isUser ? 'var(--text-accent)' : 'var(--agent-active)'};">${isUser ? 'AN' : 'K'}</div>
            <div class="message-content">
                <span class="message-sender">${sender}</span>
                <div class="message-bubble">${formattedText}</div>
            </div>
        `;
        wrapper.appendChild(messageDiv);
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }

    window.copyCodeBlock = (button) => {
        const pre = button.parentElement.nextElementSibling;
        const code = pre.querySelector('code').innerText;
        navigator.clipboard.writeText(code).then(() => {
            button.textContent = "Copied!";
            button.style.color = "var(--color-completed)";
            setTimeout(() => {
                button.textContent = "Copy";
                button.style.color = "";
            }, 2000);
        });
    };

    function triggerAIResponse(userInput) {
        const wrapper = document.querySelector('.chat-messages .chat-wrapper');

        const typingDiv = document.createElement('div');
        typingDiv.className = 'message system';
        typingDiv.id = 'chat-typing-indicator';
        typingDiv.innerHTML = `
            <div class="avatar" style="background-color: var(--agent-active)">K</div>
            <div class="message-content">
                <span class="message-sender">KRYON Core</span>
                <div class="message-bubble" style="padding: 12px 18px;">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            </div>
        `;
        wrapper.appendChild(typingDiv);
        chatFeed.scrollTop = chatFeed.scrollHeight;

        setTimeout(() => {
            typingDiv.remove();
            let aiText = `I have received your query regarding your targets. Let's analyze.`;

            const lowerInput = userInput.toLowerCase();
            if (lowerInput.includes('run') || lowerInput.includes('playbook') || lowerInput.includes('puppeteer')) {
                aiText = `To orchestrator automated cybersecurity workflows, please launch **Mode 2: Puppeteering** in the header.
Here is an example structure of the KRYON execution playbook pipeline:
\`\`\`yaml
playbook: External Security Audit
targets:
  - name: Target-Alpha
    subnet: 192.168.42.0/24
stages:
  - passive_recon
  - active_recon
  - hypothesis_generation
  - exploit_research # requires approval
  - validation
\`\`\``;
            } else if (lowerInput.includes('recon') || lowerInput.includes('nmap')) {
                aiText = `For reconnaissance, KRYON activates **Passive Recon** (using OSINT and DNS APIs) followed by **Active Recon** (utilizing tools like \`nmap\` and banner grabbers).
The gathered findings are directly aggregated into the **Intelligence Core**.
You can track service detections and vulnerabilities live.`;
            } else {
                aiText = `I've mapped the security status profile of \`Target-Alpha\`. Currently standing by in the central environment.
If you'd like to initiate an active playbook to scan and assess port availability and defensive posture, run Mode 2.
Here is the command pattern to interact with local agents directly:
\`\`\`bash
kryon-cli --target 192.168.42.100 --playbook assessment_v4.yml --oversight
\`\`\``;
            }

            appendMessage("KRYON Core", aiText);
        }, 1500);
    }

    function handleChatSend() {
        const text = chatInput.value.trim();
        if (!text && !hasAttachment) return;

        let displayMsg = text;
        if (hasAttachment) {
            displayMsg += `\n\n*(Uploaded file: target_ips.txt)*`;
            hasAttachment = false;
            attachmentPreview.style.display = 'none';
            chatInput.placeholder = "Type a message or load a playbook (Ctrl + Enter to send)...";
        }

        appendMessage("Security Analyst", displayMsg, true);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        triggerAIResponse(text);
    }

    chatSendBtn.addEventListener('click', handleChatSend);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChatSend();
        }
    });

    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = (chatInput.scrollHeight - 16) + 'px';
    });


    // --- 4. Mode 2: Puppeteering Visualization Setup ---
    const agentsData = {
        1: { name: "Passive Recon", color: "var(--agent-passive)", persona: "Calm, observant, curious. Slow rotation, scans incoming data.", status: "idle", confidence: 98, objective: "Collect external intelligence assets.", subgoal: "Gather DNS and OSINT records.", evidence: "Subnets, DNS entries.", decision: "Awaiting activation", action: "Query search engines", tools: ["WHOIS", "DNS Enum", "Shodan API", "OSINT Scraper"] },
        2: { name: "Active Recon", color: "var(--agent-active)", persona: "Energetic and alert. Fast pulsing scans.", status: "idle", confidence: 95, objective: "Scan target hosts and map networks.", subgoal: "Map open ports and banners.", evidence: "IP scopes.", decision: "Awaiting activation", action: "Run service sweeps", tools: ["Nmap Scan", "Banner Grab", "Web Directory", "OS Prober"] },
        3: { name: "Hypothesis Gen", color: "var(--agent-hypothesis)", persona: "Analytical and thoughtful. Expansion and data correlation.", status: "idle", confidence: 89, objective: "Compile potential vector paths.", subgoal: "Correlate reconnaissance data.", evidence: "Findings cache.", decision: "Awaiting activation", action: "Map entry vectors", tools: ["CVSS Scorer", "Asset Binder", "Path Finder", "Vector Mapper"] },
        4: { name: "Exploit Research", color: "var(--agent-exploit)", persona: "Experimental and confident. Snap tilts and quick reactions.", status: "idle", confidence: 82, objective: "Identify exploits for mapped ports.", subgoal: "Formulate remote scripts.", evidence: "Attack vectors.", decision: "Awaiting activation", action: "Draft exploit codes", tools: ["Compiler", "Payload Vault", "Shell Builder", "Fuzzing Tool"] },
        5: { name: "Post-Exploit", color: "var(--agent-post)", persona: "Tactical and confident. Controlled translations.", status: "idle", confidence: 85, objective: "Secure privilege escalation safely.", subgoal: "Assess environment context.", evidence: "Session shell.", decision: "Awaiting activation", action: "Audit privileges", tools: ["PrivEsc Audit", "Domain Mapper", "Cred Harvester", "Lateral Mover"] },
        6: { name: "Verification", color: "var(--agent-verify)", persona: "Skeptical and precise. Orbiting element checks.", status: "idle", confidence: 94, objective: "Ensure findings are false-positive free.", subgoal: "Run safety controls.", evidence: "Exploitation logs.", decision: "Awaiting activation", action: "Verify shell output", tools: ["Hash Auditor", "Callback Listen", "Safe Runner", "FP Filter"] },
        7: { name: "Blue Teaming", color: "var(--agent-blue)", persona: "Calm and defensive. Shield-pulse containment.", status: "idle", confidence: 91, objective: "Generate Sigma protection rules.", subgoal: "Construct IOC detection logic.", evidence: "Attack patterns.", decision: "Awaiting activation", action: "Compile mitigations", tools: ["Sigma Builder", "YARA Matcher", "Threat Hunter", "Firewall Set"] },
        8: { name: "Report Gen", color: "var(--agent-report)", persona: "Organized and precise. Glances completed files.", status: "idle", confidence: 99, objective: "Compile executive security report.", subgoal: "Format compliance metrics.", evidence: "Consolidated steps.", decision: "Awaiting activation", action: "Build PDF layouts", tools: ["PDF Compiler", "Stats Aggregator", "Writer Core", "YARA Exporter"] }
    };

    const canvasView = document.getElementById('canvas-view');
    const agentAnchors = document.querySelectorAll('.agent-node-anchor');

    function updateOrchestratorLayout() {
        const rect = canvasView.getBoundingClientRect();
        const centerX = rect.width / 2;
        const centerY = rect.height / 2 - 30;
        const radiusX = rect.width * 0.38;
        const radiusY = rect.height * 0.32;

        agentAnchors.forEach((anchor) => {
            const id = parseInt(anchor.getAttribute('data-id'));
            const angle = ((id - 1) * (2 * Math.PI) / 8) - (Math.PI / 2);

            const x = centerX + radiusX * Math.cos(angle) - 40;
            const y = centerY + radiusY * Math.sin(angle) - 45;

            anchor.style.left = `${x}px`;
            anchor.style.top = `${y}px`;
        });
    }

    agentAnchors.forEach(anchor => {
        const id = anchor.getAttribute('data-id');
        const color = agentsData[id].color;
        anchor.querySelectorAll('.face').forEach(face => {
            face.style.setProperty('--agent-accent', color);
        });
        anchor.querySelectorAll('.eye').forEach(eye => {
            eye.style.setProperty('--agent-accent', color);
        });
    });

    window.addEventListener('resize', () => {
        updateOrchestratorLayout();
        drawTentacles();
    });

    const tentacleCanvas = document.getElementById('tentacle-canvas');

    function drawTentacles() {
        tentacleCanvas.innerHTML = '';
        const canvasRect = canvasView.getBoundingClientRect();
        const octopusNode = document.getElementById('octopus-core');
        const octRect = octopusNode.getBoundingClientRect();

        const octCenterX = octRect.left - canvasRect.left + octRect.width / 2;
        const octCenterY = octRect.top - canvasRect.top + octRect.height / 2;

        agentAnchors.forEach(anchor => {
            const id = anchor.getAttribute('data-id');
            const agentRect = anchor.getBoundingClientRect();
            const agentCenterX = agentRect.left - canvasRect.left + agentRect.width / 2;
            const agentCenterY = agentRect.top - canvasRect.top + agentRect.height / 2 - 12;

            const dx = agentCenterX - octCenterX;
            const dy = agentCenterY - octCenterY;

            const cx = octCenterX + dx * 0.2 - dy * 0.1;
            const cy = octCenterY + dy * 0.2 + dx * 0.1;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const d = `M ${octCenterX} ${octCenterY} Q ${cx} ${cy} ${agentCenterX} ${agentCenterY}`;
            path.setAttribute('d', d);
            path.setAttribute('class', 'tentacle-path');
            path.setAttribute('id', `tentacle-path-${id}`);
            path.setAttribute('style', `--active-color: ${agentsData[id].color}`);

            const pulsePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            pulsePath.setAttribute('d', d);
            pulsePath.setAttribute('class', 'tentacle-pulse-path');
            pulsePath.setAttribute('id', `tentacle-pulse-${id}`);
            pulsePath.setAttribute('style', `--active-color: ${agentsData[id].color}`);

            if (agentsData[id].status === 'running') {
                path.classList.add('active');
                pulsePath.classList.add('pulsing');
            } else if (agentsData[id].status === 'completed') {
                path.style.stroke = 'var(--color-completed)';
            }

            tentacleCanvas.appendChild(path);
            tentacleCanvas.appendChild(pulsePath);
        });
    }

    // --- 5. Playbook Configuration Handlers ---
    const playbookSetupPanel = document.getElementById('playbook-setup-panel');
    const targetInput = document.getElementById('setup-target-input');
    const inScopeInput = document.getElementById('setup-in-scope');
    const offScopeInput = document.getElementById('setup-off-scope');
    const limitationsInput = document.getElementById('setup-limitations');
    const setupRunTrigger = document.getElementById('setup-run-trigger');

    const headerTarget = document.getElementById('header-target');
    const mcTargetTitle = document.getElementById('mc-profile-target-title');
    const mcInScope = document.getElementById('mc-profile-in-scope');
    const mcOffScope = document.getElementById('mc-profile-off-scope');
    const mcLimitations = document.getElementById('mc-profile-limitations');
    const repTargetTxt = document.getElementById('rep-target-txt');

    let configuredTarget = "";

    function submitPlaybookConfig() {
        configuredTarget = targetInput.value.trim() || "Target-Alpha";
        headerTarget.textContent = configuredTarget;
        mcTargetTitle.textContent = `Target: ${configuredTarget}`;
        mcInScope.textContent = `In-Scope: ${inScopeInput.value.trim() || 'Awaiting setup parameters...'}`;
        mcOffScope.textContent = `Excludes: ${offScopeInput.value.trim() || 'Awaiting setup parameters...'}`;
        mcLimitations.textContent = `Safeguards: ${limitationsInput.value.trim() || 'Awaiting setup parameters...'}`;
        repTargetTxt.textContent = configuredTarget;

        // Hide config card
        playbookSetupPanel.style.display = 'none';

        // Trigger Run
        startCyberRun();
    }

    setupRunTrigger.addEventListener('click', submitPlaybookConfig);

    // --- 6. Puppeteer Simulation Orchestrator (15s sequence) ---
    const launchBtn = document.getElementById('op-btn-launch');
    const pauseBtn = document.getElementById('op-btn-pause');
    const stopBtn = document.getElementById('op-btn-stop');
    const headerStatus = document.getElementById('header-status');
    const headerClock = document.getElementById('header-clock');
    const headerAgents = document.getElementById('header-agents');

    const coreFindings = document.getElementById('core-findings');
    const coreDomains = document.getElementById('core-domains');
    const coreServices = document.getElementById('core-services');
    const corePaths = document.getElementById('core-paths');
    const coreContainer = document.getElementById('intelligence-core');

    const reviewBanner = document.getElementById('review-banner');
    const oversightApprove = document.getElementById('oversight-approve-btn');
    const oversightDeny = document.getElementById('oversight-deny-btn');

    const mcProgressPct = document.getElementById('mc-progress-pct');
    const mcProgressBar = document.getElementById('mc-progress-bar');
    const mcActiveCount = document.getElementById('mc-active-count');
    const mcFindingsCount = document.getElementById('mc-findings-count');
    const mcLogFeed = document.getElementById('mc-log-feed');

    let runStatus = 'idle';
    let secondsElapsed = 0;
    let clockInterval = null;
    let simulationTimeout = null;
    let activeAgentCount = 0;

    let findingsCount = 0;
    let domainsCount = 0;
    let servicesCount = 0;
    let pathsCount = 0;

    let simulationStepIndex = 0;

    function formatClockTime(sec) {
        const mins = Math.floor(sec / 60).toString().padStart(2, '0');
        const secs = (sec % 60).toString().padStart(2, '0');
        return `${mins}:${secs}`;
    }

    function updateSimulationClock() {
        secondsElapsed++;
        headerClock.textContent = formatClockTime(secondsElapsed);
    }

    function appendOpLog(sourceId, msg) {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        const timeStr = formatClockTime(secondsElapsed);

        let color = 'var(--text-accent)';
        let sourceName = 'SYSTEM';
        if (sourceId === 'octopus') {
            sourceName = 'ORCHESTRATOR';
            color = 'var(--text-accent)';
        } else if (sourceId === 'core') {
            sourceName = 'INTEL CORE';
            color = 'var(--agent-hypothesis)';
        } else if (sourceId) {
            sourceName = agentsData[sourceId].name;
            color = agentsData[sourceId].color;
        }

        logEntry.innerHTML = `
            <span class="log-time">[${timeStr}]</span>
            <span class="log-source" style="--agent-accent: ${color}">${sourceName}</span>
            <span class="log-msg">${msg}</span>
        `;
        mcLogFeed.appendChild(logEntry);
        mcLogFeed.scrollTop = mcLogFeed.scrollHeight;
    }

    function setAgentState(id, state) {
        agentsData[id].status = state;
        const cubeContainer = document.getElementById(`cube-container-${id}`);

        cubeContainer.classList.remove('running', 'waiting', 'completed', 'needs-review', 'error');
        if (state !== 'idle') {
            cubeContainer.classList.add(state);
        }

        if (state === 'running') {
            activeAgentCount++;
        } else if (state === 'completed' || state === 'idle' || state === 'needs-review') {
            if (activeAgentCount > 0) activeAgentCount--;
        }

        headerAgents.textContent = `${activeAgentCount} / 8 ACTIVE`;
        mcActiveCount.textContent = activeAgentCount;

        if (selectedAgentId === parseInt(id)) {
            populateAgentDetailPanel(id);
        }

        drawTentacles();
    }

    function emitFlowParticle(fromX, fromY, toX, toY, color) {
        const particle = document.createElement('div');
        particle.className = 'flow-particle';
        particle.style.backgroundColor = color;
        particle.style.boxShadow = `0 0 6px ${color}`;
        canvasView.appendChild(particle);

        const startTime = performance.now();
        const duration = 1200;

        function step(now) {
            const progress = Math.min((now - startTime) / duration, 1);
            const currX = fromX + (toX - fromX) * progress;
            const currY = fromY + (toY - fromY) * progress;

            particle.style.left = `${currX}px`;
            particle.style.top = `${currY}px`;

            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                particle.remove();
            }
        }
        requestAnimationFrame(step);
    }

    function emitParticlesFromAgentToCore(agentId) {
        const canvasRect = canvasView.getBoundingClientRect();
        const agentRect = document.querySelector(`.agent-node-anchor[data-id="${agentId}"]`).getBoundingClientRect();
        const coreRect = coreContainer.getBoundingClientRect();

        const fromX = agentRect.left - canvasRect.left + agentRect.width / 2;
        const fromY = agentRect.top - canvasRect.top + agentRect.height / 2;
        const toX = coreRect.left - canvasRect.left + coreRect.width / 2;
        const toY = coreRect.top - canvasRect.top + coreRect.height / 2;

        const color = agentsData[agentId].color;

        for (let i = 0; i < 6; i++) {
            setTimeout(() => {
                emitFlowParticle(fromX, fromY, toX, toY, color);
            }, i * 200);
        }
    }

    function emitPulseFromCoreToAgent(agentId) {
        const canvasRect = canvasView.getBoundingClientRect();
        const agentRect = document.querySelector(`.agent-node-anchor[data-id="${agentId}"]`).getBoundingClientRect();
        const coreRect = coreContainer.getBoundingClientRect();

        const fromX = coreRect.left - canvasRect.left + coreRect.width / 2;
        const fromY = coreRect.top - canvasRect.top + coreRect.height / 2;
        const toX = agentRect.left - canvasRect.left + agentRect.width / 2;
        const toY = agentRect.top - canvasRect.top + agentRect.height / 2;

        const color = agentsData[agentId].color;

        for (let i = 0; i < 4; i++) {
            setTimeout(() => {
                emitFlowParticle(fromX, fromY, toX, toY, color);
            }, i * 150);
        }
    }

    function animateCoreCounters(targetFindings, targetDomains, targetServices, targetPaths) {
        coreContainer.classList.add('active-pulse');
        setTimeout(() => coreContainer.classList.remove('active-pulse'), 800);

        const startFindings = findingsCount;
        const startDomains = domainsCount;
        const startServices = servicesCount;
        const startPaths = pathsCount;

        const duration = 1500;
        const startTime = performance.now();

        function step(now) {
            const progress = Math.min((now - startTime) / duration, 1);
            findingsCount = Math.floor(startFindings + (targetFindings - startFindings) * progress);
            domainsCount = Math.floor(startDomains + (targetDomains - startDomains) * progress);
            servicesCount = Math.floor(startServices + (targetServices - startServices) * progress);
            pathsCount = Math.floor(startPaths + (targetPaths - startPaths) * progress);

            coreFindings.textContent = findingsCount;
            coreDomains.textContent = domainsCount;
            coreServices.textContent = servicesCount;
            corePaths.textContent = pathsCount;
            mcFindingsCount.textContent = findingsCount;

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }
        requestAnimationFrame(step);
    }

    function updateProgressBar(percent) {
        mcProgressPct.textContent = `${percent}%`;
        mcProgressBar.style.width = `${percent}%`;
    }

    function highlightPipelineStep(stepId, colorClass) {
        document.querySelectorAll('.pipeline-step').forEach(step => {
            step.classList.remove('active', 'completed');
            step.style.removeProperty('--step-color');
        });

        for (let i = 1; i < stepId; i++) {
            document.getElementById(`step-lbl-${i}`).classList.add('completed');
        }

        const activeStep = document.getElementById(`step-lbl-${stepId}`);
        if (activeStep) {
            activeStep.classList.add('active');
            activeStep.style.setProperty('--step-color', colorClass);
        }
    }

    function executePipelineStep() {
        if (runStatus !== 'running') return;

        switch (simulationStepIndex) {
            case 0:
                appendOpLog('octopus', "Central Orchestrator wake-up pulses initiated.");
                document.getElementById('octopus-core').classList.replace('idle', 'waking');

                simulationTimeout = setTimeout(() => {
                    document.getElementById('octopus-core').classList.replace('waking', 'running');
                    simulationStepIndex = 1;
                    executePipelineStep();
                }, 1200);
                break;

            case 1:
                setAgentState(1, 'running');
                highlightPipelineStep(1, agentsData[1].color);
                appendOpLog(1, "OSINT collections initiated against target DNS endpoints.");
                emitParticlesFromAgentToCore(1);

                simulationTimeout = setTimeout(() => {
                    animateCoreCounters(34, 12, 0, 0);
                    appendOpLog('core', "+12 root domains registered into findings cache.");
                    setAgentState(1, 'completed');

                    simulationStepIndex = 2;
                    executePipelineStep();
                }, 2500);
                break;

            case 2:
                setAgentState(2, 'running');
                appendOpLog(2, "Active sweeps mapping subnet host ports.");
                emitParticlesFromAgentToCore(2);

                simulationTimeout = setTimeout(() => {
                    animateCoreCounters(96, 43, 18, 0);
                    appendOpLog('core', "+18 exposed sub-services matched with banner indices.");
                    setAgentState(2, 'completed');

                    setTimeout(() => {
                        appendOpLog('core', "Reconnaissance completed. Streaming data to Hypothesis Gen.");
                        emitPulseFromCoreToAgent(3);
                    }, 500);

                    simulationStepIndex = 3;
                    executePipelineStep();
                }, 2800);
                break;

            case 3:
                setAgentState(3, 'running');
                highlightPipelineStep(2, agentsData[3].color);
                appendOpLog(3, "Correlating port mapping database with vulnerability definitions.");

                simulationTimeout = setTimeout(() => {
                    animateCoreCounters(127, 43, 18, 6);
                    appendOpLog('core', "Hypothesis model maps 6 potential exploit vectors.");
                    setAgentState(3, 'completed');

                    simulationStepIndex = 4;
                    executePipelineStep();
                }, 2200);
                break;

            case 4:
                setAgentState(4, 'running');
                highlightPipelineStep(3, agentsData[4].color);
                appendOpLog(4, "Testing remote execution exploit payload (WinRM default creds)...");

                simulationTimeout = setTimeout(() => {
                    runStatus = 'paused';
                    headerStatus.textContent = "● NEEDS REVIEW";
                    headerStatus.className = "opp-meta-val needs-review";
                    setAgentState(4, 'needs-review');

                    reviewBanner.style.display = 'flex';
                    appendOpLog('octopus', "CRITICAL SAFELOCKED GATE MET: Human review required before exploit payload execution.");
                }, 1800);
                break;

            case 5:
                setAgentState(4, 'completed');
                setAgentState(5, 'running');
                highlightPipelineStep(4, agentsData[5].color);
                appendOpLog(5, "Safe sandbox shell confirmed. Indexing administrative user hashes.");

                simulationTimeout = setTimeout(() => {
                    setAgentState(5, 'completed');
                    simulationStepIndex = 6;
                    executePipelineStep();
                }, 2000);
                break;

            case 6:
                setAgentState(6, 'running');
                highlightPipelineStep(5, agentsData[6].color);
                appendOpLog(6, "Validating shell session outputs against potential mock vulnerabilities.");

                simulationTimeout = setTimeout(() => {
                    setAgentState(6, 'completed');
                    simulationStepIndex = 7;
                    executePipelineStep();
                }, 2000);
                break;

            case 7:
                setAgentState(7, 'running');
                highlightPipelineStep(6, agentsData[7].color);
                appendOpLog(7, "Formulating custom protective YARA scripts and host Sigma rules.");

                simulationTimeout = setTimeout(() => {
                    setAgentState(7, 'completed');
                    simulationStepIndex = 8;
                    executePipelineStep();
                }, 2000);
                break;

            case 8:
                setAgentState(8, 'running');
                highlightPipelineStep(7, agentsData[8].color);
                appendOpLog(8, "Aggregating findings dashboard into standard compliance reports.");

                simulationTimeout = setTimeout(() => {
                    setAgentState(8, 'completed');

                    document.getElementById('octopus-core').classList.replace('running', 'idle');

                    runStatus = 'complete';
                    headerStatus.textContent = "● COMPLETE";
                    headerStatus.className = "opp-meta-val";

                    pauseBtn.disabled = true;
                    stopBtn.disabled = true;
                    launchBtn.disabled = false;

                    clearInterval(clockInterval);
                    updateProgressBar(100);
                    appendOpLog('octopus', "Autonomous Security Playbook Run COMPLETED. Findings packaging finished.");

                    setTimeout(() => {
                        document.getElementById('report-modal').style.display = 'flex';
                    }, 800);
                }, 2200);
                break;
        }

        if (simulationStepIndex > 0 && runStatus === 'running') {
            const totalSteps = 8;
            const progressPercent = Math.floor((simulationStepIndex / totalSteps) * 90);
            updateProgressBar(progressPercent);
        }
    }

    function triggerLaunchSequence() {
        // If config target is blank, open target dialog panel
        if (!configuredTarget) {
            playbookSetupPanel.style.display = 'flex';
        } else {
            startCyberRun();
        }
    }

    function startCyberRun() {
        runStatus = 'running';
        simulationStepIndex = 0;
        secondsElapsed = 0;
        activeAgentCount = 0;

        findingsCount = 0;
        domainsCount = 0;
        servicesCount = 0;
        pathsCount = 0;

        coreFindings.textContent = "0";
        coreDomains.textContent = "0";
        coreServices.textContent = "0";
        corePaths.textContent = "0";

        headerStatus.textContent = "● RUNNING";
        headerStatus.className = "opp-meta-val running";
        headerClock.textContent = "00:00";

        launchBtn.disabled = true;
        pauseBtn.disabled = false;
        stopBtn.disabled = false;

        reviewBanner.style.display = 'none';

        for (let i = 1; i <= 8; i++) {
            setAgentState(i, 'idle');
        }

        updateProgressBar(0);

        mcLogFeed.innerHTML = '';
        appendOpLog('octopus', `Deploying KRYON Orchestration playbook against ${configuredTarget}`);

        clearInterval(clockInterval);
        clockInterval = setInterval(updateSimulationClock, 1000);

        executePipelineStep();
    }

    function approveHumanGate() {
        if (runStatus !== 'paused') return;

        reviewBanner.style.display = 'none';
        runStatus = 'running';
        headerStatus.textContent = "● RUNNING";
        headerStatus.className = "opp-meta-val running";

        appendOpLog('octopus', "Oversight: operator APPROVED WinRM remote payload execution.");

        simulationStepIndex = 5;
        executePipelineStep();
    }

    function denyHumanGate() {
        if (runStatus !== 'paused') return;

        reviewBanner.style.display = 'none';
        stopCyberRun();
        appendOpLog('octopus', "Oversight: operator DENIED payload deployment. Playbook run aborted.");
        setAgentState(4, 'error');
    }

    function stopCyberRun() {
        runStatus = 'idle';
        headerStatus.textContent = "● IDLE";
        headerStatus.className = "opp-meta-val";

        launchBtn.disabled = false;
        pauseBtn.disabled = true;
        stopBtn.disabled = true;

        clearInterval(clockInterval);
        clearTimeout(simulationTimeout);
        reviewBanner.style.display = 'none';

        // Reset configuration parameters
        configuredTarget = "";
        headerTarget.textContent = "None Configured";
        playbookSetupPanel.style.display = 'flex';

        for (let i = 1; i <= 8; i++) {
            setAgentState(i, 'idle');
        }

        document.getElementById('octopus-core').className = 'octopus-orchestrator idle';
        appendOpLog('octopus', "Operator requested manual TERMINATION. All pipelines aborted.");
        updateProgressBar(0);
    }

    launchBtn.addEventListener('click', triggerLaunchSequence);
    stopBtn.addEventListener('click', stopCyberRun);
    oversightApprove.addEventListener('click', approveHumanGate);
    oversightDeny.addEventListener('click', denyHumanGate);

    // --- 7. Agent Split Panel click handler ---
    const missionControlPanel = document.getElementById('mission-control-panel');
    const agentDetailPanel = document.getElementById('agent-detail-panel');
    const closeDetailBtn = document.getElementById('close-detail-btn');
    let selectedAgentId = null;

    function populateAgentDetailPanel(id) {
        const data = agentsData[id];
        document.getElementById('detail-agent-name').textContent = data.name;
        document.getElementById('detail-agent-persona').textContent = data.persona;

        const header = document.getElementById('detail-identity-header');
        header.style.borderBottom = `2px solid ${data.color}`;
        document.getElementById('detail-mini-cube').style.setProperty('--agent-accent', data.color);

        const statusBadge = document.getElementById('detail-agent-badge');
        const statusText = document.getElementById('detail-agent-status');
        statusText.textContent = data.status;
        statusBadge.style.setProperty('--status-color', `var(--color-${data.status})`);

        document.getElementById('reasoning-objective').textContent = data.objective;
        document.getElementById('reasoning-subgoal').textContent = data.subgoal;
        document.getElementById('reasoning-evidence').textContent = data.evidence;
        document.getElementById('reasoning-decision').textContent = data.decision;
        document.getElementById('reasoning-action').textContent = data.action;

        const fill = document.getElementById('confidence-circle-fill');
        const text = document.getElementById('confidence-text');
        fill.style.setProperty('--agent-accent', data.color);

        const confidence = data.confidence;
        const offset = 126 - (126 * confidence) / 100;
        fill.style.strokeDashoffset = offset;
        text.textContent = `${confidence}%`;

        document.getElementById('detail-tool-count').textContent = `${data.tools.length} Tools Available`;
        drawToolGraph(data.tools, data.color);
    }

    function drawToolGraph(tools, accentColor) {
        const svg = document.getElementById('tool-svg-canvas');
        const nodesContainer = document.getElementById('tool-node-container');

        svg.innerHTML = '';
        nodesContainer.innerHTML = '';

        const rect = svg.getBoundingClientRect();
        const startX = 24;
        const startY = rect.height / 2;
        const rightX = rect.width - 150;

        tools.forEach((tool, index) => {
            const childY = 16 + index * 40;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const d = `M ${startX} ${startY} H ${startX + 40} V ${childY} H ${rightX}`;
            path.setAttribute('d', d);
            path.setAttribute('class', 'tool-link');
            path.setAttribute('id', `tool-link-${index}`);
            path.setAttribute('style', `--agent-accent: ${accentColor}`);
            svg.appendChild(path);

            const node = document.createElement('div');
            node.className = 'tool-node';
            node.setAttribute('id', `tool-node-${index}`);
            node.style.left = `${rightX}px`;
            node.style.top = `${childY - 18}px`;

            node.innerHTML = `
                <span class="tool-node-name">${tool}</span>
                <span class="tool-node-status" id="tool-node-status-${index}">Standby</span>
            `;
            nodesContainer.appendChild(node);
        });

        if (runStatus === 'running' || runStatus === 'paused') {
            const activeIndex = 1;
            const node = document.getElementById(`tool-node-${activeIndex}`);
            const link = document.getElementById(`tool-link-${activeIndex}`);
            const status = document.getElementById(`tool-node-status-${activeIndex}`);

            if (node) {
                node.classList.add('active');
                node.style.setProperty('--agent-accent', accentColor);
            }
            if (link) {
                link.classList.add('active');
            }
            if (status) {
                status.textContent = 'ACTIVE';
            }
            document.getElementById('active-tool-name').textContent = tools[activeIndex];
            document.getElementById('active-tool-status').textContent = 'EXECUTING SUB-PROCESS';
            document.getElementById('active-tool-result').textContent = '200 OK';
        } else {
            document.getElementById('active-tool-name').textContent = '-';
            document.getElementById('active-tool-status').textContent = 'STANDBY';
            document.getElementById('active-tool-result').textContent = '-';
        }
    }

    agentAnchors.forEach(anchor => {
        anchor.addEventListener('click', () => {
            const id = parseInt(anchor.getAttribute('data-id'));
            selectedAgentId = id;

            agentAnchors.forEach(n => n.classList.remove('selected'));
            anchor.classList.add('selected');

            missionControlPanel.style.display = 'none';
            agentDetailPanel.style.display = 'flex';

            populateAgentDetailPanel(id);
        });
    });

    closeDetailBtn.addEventListener('click', () => {
        selectedAgentId = null;
        agentAnchors.forEach(n => n.classList.remove('selected'));

        missionControlPanel.style.display = 'flex';
        agentDetailPanel.style.display = 'none';
    });

    // --- 8. Final Report Modal and Exports ---
    const reportModal = document.getElementById('report-modal');
    const closeReportBtn = document.getElementById('close-report-modal-btn');
    const exportPdf = document.getElementById('rep-export-pdf');
    const exportJson = document.getElementById('rep-export-json');
    const exportYara = document.getElementById('rep-export-yara');

    closeReportBtn.addEventListener('click', () => {
        reportModal.style.display = 'none';
    });

    function mockExportAction(filename) {
        alert(`Generating export: ${filename}\nExport complete. Saved to workspace.`);
    }

    exportPdf.addEventListener('click', () => mockExportAction('KRYON_Audit_Report.pdf'));
    exportJson.addEventListener('click', () => mockExportAction('kryon_findings.json'));
    exportYara.addEventListener('click', () => mockExportAction('kryon_defense_rules.yara'));

    // --- 9. Initialize System ---
    updateOrchestratorLayout();
    setTimeout(drawTentacles, 100);
});
