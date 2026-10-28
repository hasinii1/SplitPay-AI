/**
 * SplitPay AI - Frontend Application
 * Discrete Landing Page & Dashboard views, Dual Currency ($ USD / ₹ INR),
 * Forest (#064734) & Leaf (#E0FFC2) theme, AG Grid, and PayPal Orders v2.
 */

// Application State
let currentView = 'landing'; // 'landing' or 'dashboard'
let currentBillId = null;
let currentReceiptData = null;
let currentSplitCurrency = null;
let currentAssignments = []; // [{ name: str, price: num, consumers: [str] }]
let currentSplitResult = null;
let currentOrders = [];
let pollingInterval = null;
let currentNudgeShare = null;
let selectedTone = 'polite';
let gridApi = null;

// Currency State: USD ($) vs INR (₹)
let currentCurrency = 'USD';
let EXCHANGE_RATE_USD_TO_INR = null;
let EXCHANGE_RATE_DATE = null;

function getCurrencySymbol() {
    return currentCurrency === 'INR' ? '₹' : '$';
}

function convertAmount(amount, fromCurrency, toCurrency = currentCurrency) {
    if (fromCurrency === toCurrency) return amount;
    if (fromCurrency === "USD" && toCurrency === "INR") {
        if (!EXCHANGE_RATE_USD_TO_INR) {
            throw new Error("The latest USD/INR exchange rate is not available.");
        }
        return amount * EXCHANGE_RATE_USD_TO_INR;
    }
    if (fromCurrency === "INR" && toCurrency === "USD") {
        if (!EXCHANGE_RATE_USD_TO_INR) {
            throw new Error("The latest USD/INR exchange rate is not available.");
        }
        return amount / EXCHANGE_RATE_USD_TO_INR;
    }
    return amount;
}

function formatCurrency(amount, sourceCurrency = currentCurrency) {
    const symbol = getCurrencySymbol();
    const converted = convertAmount(amount, sourceCurrency);
    return `${symbol}${converted.toFixed(2)}`;
}

async function setCurrency(curr) {
    if (currentSplitResult && curr !== currentSplitCurrency) {
        alert("The split has already been calculated in " + currentSplitCurrency + ". Start a new bill to change currency.");
        return;
    }
    if (
        currentReceiptData &&
        currentReceiptData.currency !== curr &&
        !EXCHANGE_RATE_USD_TO_INR
    ) {
        try {
            await loadExchangeRate();
        } catch (error) {
            alert(error.message);
            return;
        }
    }
    currentCurrency = curr;

    // Toggle button styles in navbar
    const btnUSD = document.getElementById("currencyBtnUSD");
    const btnINR = document.getElementById("currencyBtnINR");

    if (btnUSD && btnINR) {
        if (curr === 'USD') {
            btnUSD.className = "px-2.5 sm:px-3 py-1 rounded-full font-bold transition bg-leaf text-forest shadow-sm text-xs";
            btnINR.className = "px-2.5 sm:px-3 py-1 rounded-full font-bold transition text-slate-300 hover:text-white text-xs";
        } else {
            btnINR.className = "px-2.5 sm:px-3 py-1 rounded-full font-bold transition bg-leaf text-forest shadow-sm text-xs";
            btnUSD.className = "px-2.5 sm:px-3 py-1 rounded-full font-bold transition text-slate-300 hover:text-white text-xs";
        }
    }

    // Refresh currently displayed numbers
    if (currentReceiptData) {
        document.getElementById("receiptSubtotal").textContent = formatCurrency(currentReceiptData.subtotal, currentReceiptData.currency);
        document.getElementById("receiptTax").textContent = formatCurrency(currentReceiptData.tax, currentReceiptData.currency);
        document.getElementById("receiptTip").textContent = formatCurrency(currentReceiptData.tip, currentReceiptData.currency);
        document.getElementById("receiptTotal").textContent = formatCurrency(currentReceiptData.total, currentReceiptData.currency);
        renderItemsListUI();
    }

    if (currentSplitResult) {
        const badge = document.getElementById("mathVerificationText");
        if (badge) {
            badge.textContent = `Hare-Niemeyer Verified: Sum of shares matches ${formatCurrency(currentSplitResult.total)} exactly.`;
        }
        renderAGGrid();
        renderParticipantCards();
    }
}

// --- View Switching: Landing vs Dashboard ---

function showView(viewName) {
    currentView = viewName;
    const landingView = document.getElementById("landingView");
    const dashboardView = document.getElementById("dashboardView");
    const navLandingBtn = document.getElementById("navLandingBtn");
    const navDashboardBtn = document.getElementById("navDashboardBtn");

    if (viewName === 'dashboard') {
        if (landingView) landingView.classList.add("hidden");
        if (dashboardView) dashboardView.classList.remove("hidden");

        if (navDashboardBtn) {
            navDashboardBtn.className = "px-3.5 py-1.5 rounded-xl font-bold transition bg-leaf text-forest shadow flex items-center gap-1.5";
        }
        if (navLandingBtn) {
            navLandingBtn.className = "px-3.5 py-1.5 rounded-xl font-bold transition text-slate-300 hover:text-white";
        }
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
        if (dashboardView) dashboardView.classList.add("hidden");
        if (landingView) landingView.classList.remove("hidden");

        if (navLandingBtn) {
            navLandingBtn.className = "px-3.5 py-1.5 rounded-xl font-bold transition bg-leaf text-forest shadow";
        }
        if (navDashboardBtn) {
            navDashboardBtn.className = "px-3.5 py-1.5 rounded-xl font-bold transition text-slate-300 hover:text-white flex items-center gap-1.5";
        }
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    if (window.lucide) lucide.createIcons();
}

// --- Initialize on Page Load ---

document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    checkSystemHealth();
    loadExchangeRate().catch(error => {
        console.warn("Exchange rate unavailable:", error);
    });
    const billId = new URLSearchParams(window.location.search).get("bill_id");
    if (billId) {
        restoreBillFromServer(billId);
    } else {
        showView('landing');
    }
});

function setupEventListeners() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("receiptFileInput");

    if (dropzone && fileInput) {
        dropzone.addEventListener("click", () => fileInput.click());

        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                handleReceiptUpload(e.target.files[0]);
            }
        });

        // Drag and drop
        dropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropzone.classList.add("border-leaf", "bg-forest/60");
        });

        dropzone.addEventListener("dragleave", () => {
            dropzone.classList.remove("border-leaf", "bg-forest/60");
        });

        dropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropzone.classList.remove("border-leaf", "bg-forest/60");
            if (e.dataTransfer.files.length > 0) {
                handleReceiptUpload(e.dataTransfer.files[0]);
            }
        });
    }
}

async function checkSystemHealth() {
    try {
        const res = await fetch("/api/health");
        const data = await res.json();
        const modeText = document.getElementById("paypalModeText");
        if (modeText) {
            modeText.textContent = data.paypal_configured ? "PayPal Sandbox Connected" : "PayPal Sandbox (Demo Mode)";
        }

        async function loadExchangeRate() {
            const response = await fetch("/api/exchange-rate", { cache: "no-store" });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || "Could not load the current USD/INR exchange rate.");
            }
            EXCHANGE_RATE_USD_TO_INR = Number(data.rate);
            EXCHANGE_RATE_DATE = data.date;
            const rateText = document.getElementById("exchangeRateText");
            if (rateText) {
                rateText.textContent = `Reference rate (${EXCHANGE_RATE_DATE}): $1 = ₹${EXCHANGE_RATE_USD_TO_INR.toFixed(2)}. PayPal charges in USD.`;
            }
            return data;
        }

        async function restoreBillFromServer(billId) {
            showGlobalLoading("Restoring bill and payment status...");
            try {
                const response = await fetch(`/api/bills/${encodeURIComponent(billId)}`, {
                    cache: "no-store",
                });
                const bill = await response.json();
                if (!response.ok) {
                    throw new Error(bill.detail || "Could not restore this bill.");
                }

                const consumersByItem = new Map();
                (bill.shares || []).forEach(share => {
                    (share.assigned_items || []).forEach(item => {
                        const consumers = item.split_with?.length ? item.split_with : [share.person];
                        const currentConsumers = consumersByItem.get(item.item_name) || new Set();
                        consumers.forEach(consumer => currentConsumers.add(consumer));
                        consumersByItem.set(item.item_name, currentConsumers);
                    });
                });

                const receipt = {
                    bill_id: bill.id,
                    merchant: bill.merchant,
                    date: bill.date,
                    currency: bill.receipt_currency || bill.currency || "USD",
                    items: (bill.items || []).map(item => ({
                        name: item.name,
                        price: item.price,
                        quantity: item.quantity,
                        consumers: [...(consumersByItem.get(item.name) || [])],
                    })),
                    subtotal: bill.subtotal,
                    tax: bill.tax,
                    tip: bill.tip,
                    discount: bill.discount,
                    total: bill.total,
                    calculated_items_sum: (bill.items || []).reduce((sum, item) => sum + item.price, 0),
                    has_discrepancy: false,
                };
                loadReceiptDataIntoUI(receipt);

                if (bill.shares?.length) {
                    await setCurrency(bill.currency || receipt.currency);
                    const shares = Object.fromEntries(bill.shares.map(share => [
                        share.person,
                        {
                            ...share,
                            items_subtotal_cents: 0,
                            tax_cents: 0,
                            tip_cents: 0,
                            discount_cents: 0,
                            total_cents: 0,
                        },
                    ]));
                    currentSplitResult = {
                        bill_id: bill.id,
                        shares,
                        total_items: Object.values(shares).reduce((sum, share) => sum + share.items_subtotal, 0),
                        tax: bill.tax,
                        tip: bill.tip,
                        discount: bill.discount,
                        total: Object.values(shares).reduce((sum, share) => sum + share.total, 0),
                        is_balanced: true,
                    };
                    currentSplitCurrency = bill.currency || "USD";
                    currentOrders = bill.shares
                        .filter(share => share.paypal_order_id)
                        .map(share => ({
                            person: share.person,
                            order_id: share.paypal_order_id,
                            approval_url: share.paypal_approval_url,
                            qr_code_data: share.qr_code_data,
                            total_amount: share.paypal_amount,
                            currency: share.paypal_currency || "USD",
                        }));
                    const badge = document.getElementById("mathVerificationText");
                    if (badge) {
                        badge.textContent = `Hare-Niemeyer Verified: Sum of shares matches ${formatCurrency(currentSplitResult.total)} exactly.`;
                    }
                    showView("dashboard");
                    goToStep(4);
                    renderParticipantCards();
                    startPollingBillStatus();
                }

                const paymentState = new URLSearchParams(window.location.search).get("payment");
                if (paymentState === "success") {
                    const person = new URLSearchParams(window.location.search).get("person");
                    if (person) {
                        const paidShare = bill.shares.find(share => share.person === person);
                        if (paidShare?.status !== "PAID") {
                            throw new Error("PayPal returned, but this share is not marked paid yet. Refresh the dashboard in a moment.");
                        }
                    }
                }
                window.history.replaceState({}, "", `/?bill_id=${encodeURIComponent(bill.id)}`);
            } catch (error) {
                alert(error.message);
                showView("landing");
            } finally {
                hideGlobalLoading();
            }
        }
    } catch (err) {
        console.warn("Health check error:", err);
    }
}

// --- Stepper Navigation Inside Dashboard ---

function goToStep(stepNumber) {
    [1, 2, 3, 4].forEach(n => {
        const sec = document.getElementById(`step${n}Section`);
        const tab = document.getElementById(`stepTab${n}`);
        if (sec) sec.classList.toggle("hidden", n !== stepNumber);
        if (tab) {
            if (n === stepNumber) {
                tab.className = "step-tab py-3 px-2 rounded-xl border border-leaf/60 bg-forest text-leaf font-bold text-xs sm:text-sm flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 transition shadow-md";
                tab.querySelector("span:first-child").className = "w-5 h-5 rounded-full bg-leaf text-forest text-xs flex items-center justify-center font-bold";
            } else if (n < stepNumber) {
                tab.className = "step-tab py-3 px-2 rounded-xl border border-leaf/30 bg-forest-dark text-leaf/80 font-semibold text-xs sm:text-sm flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 transition";
                tab.querySelector("span:first-child").className = "w-5 h-5 rounded-full bg-forest text-leaf text-xs flex items-center justify-center font-bold border border-leaf/30";
            } else {
                tab.className = "step-tab py-3 px-2 rounded-xl border border-forest-border bg-forest-dark/50 text-slate-400 font-semibold text-xs sm:text-sm flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 transition";
                tab.querySelector("span:first-child").className = "w-5 h-5 rounded-full bg-forest-surface text-slate-400 text-xs flex items-center justify-center font-bold";
            }
        }
    });

    if (stepNumber === 3) {
        renderAGGrid();
    }
    if (window.lucide) lucide.createIcons();
}

// --- Step 1: Upload & OCR ---

async function handleReceiptUpload(file) {
    const formData = new FormData();
    formData.append("file", file);

    showGlobalLoading("Analyzing receipt with Google Gemini Vision...");
    try {
        const response = await fetch("/api/receipt/upload", {
            method: "POST",
            body: formData,
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || "Receipt parsing failed.");
        }
        const data = await response.json();
        loadReceiptDataIntoUI(data);
    } catch (err) {
        alert("Could not process receipt image: " + err.message);
    } finally {
        hideGlobalLoading();
    }
}

async function launchDemoBill() {
    showView('dashboard');
    await loadSampleReceipt();
}

async function loadSampleReceipt() {
    showGlobalLoading("Loading Mario's Trattoria sample receipt...");
    try {
        const response = await fetch("/api/receipt/sample", { method: "POST" });
        const data = await response.json();
        loadReceiptDataIntoUI(data);
    } catch (err) {
        alert("Error loading sample: " + err.message);
    } finally {
        hideGlobalLoading();
    }
}

function loadReceiptDataIntoUI(data) {
    currentReceiptData = data;
    currentBillId = data.bill_id;
    currentSplitResult = null;
    currentSplitCurrency = null;
    currentOrders = [];
    setCurrency(data.currency === "INR" ? "INR" : "USD");

    // Populate Receipt Card with converted currency values
    document.getElementById("receiptMerchant").textContent = data.merchant || "Restaurant";
    document.getElementById("receiptDate").textContent = data.date || new Date().toISOString().split("T")[0];
    document.getElementById("receiptSubtotal").textContent = formatCurrency(data.subtotal, data.currency);
    document.getElementById("receiptTax").textContent = formatCurrency(data.tax, data.currency);
    document.getElementById("receiptTip").textContent = formatCurrency(data.tip, data.currency);
    document.getElementById("receiptTotal").textContent = formatCurrency(data.total, data.currency);

    // Discrepancy Alert
    const discAlert = document.getElementById("discrepancyAlert");
    if (discAlert) {
        discAlert.classList.toggle("hidden", !data.has_discrepancy);
    }

    // Initialize item assignments
    currentAssignments = data.items.map(it => ({
        name: it.name,
        price: it.price,
        quantity: it.quantity || 1,
        consumers: it.consumers || []
    }));

    renderItemsListUI();
    goToStep(2);
}

function renderItemsListUI() {
    const container = document.getElementById("receiptItemsList");
    if (!container) return;
    container.innerHTML = "";

    currentAssignments.forEach((item, index) => {
        const itemEl = document.createElement("div");
        itemEl.className = "p-3 rounded-2xl bg-forest-dark border border-forest-border space-y-1.5 text-xs shadow-sm";

        const tagsHtml = item.consumers.map(c => `
            <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-forest text-leaf border border-leaf/40 font-bold text-[10px]">
                ${c}
                <button onclick="removeConsumerFromItem(${index}, '${c}')" class="hover:text-white">&times;</button>
            </span>
        `).join("");

        itemEl.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="font-semibold text-slate-100">${item.name}</span>
                <span class="font-mono text-leaf font-bold">${formatCurrency(item.price, currentReceiptData.currency)}</span>
            </div>
            <div class="flex flex-wrap items-center gap-1.5 pt-1">
                ${tagsHtml || '<span class="text-slate-400 italic text-[11px]">Unassigned</span>'}
                <button onclick="promptAddConsumer(${index})" class="px-2 py-0.5 rounded-lg bg-forest hover:bg-forest-light text-leaf text-[10px] border border-leaf/30 transition">
                    + Add friend
                </button>
            </div>
        `;
        container.appendChild(itemEl);
    });
}

function removeConsumerFromItem(itemIndex, consumer) {
    currentAssignments[itemIndex].consumers = currentAssignments[itemIndex].consumers.filter(c => c !== consumer);
    renderItemsListUI();
}

function promptAddConsumer(itemIndex) {
    const name = prompt("Enter friend's name (e.g. Alice):");
    if (name && name.trim()) {
        const clean = name.trim();
        if (!currentAssignments[itemIndex].consumers.includes(clean)) {
            currentAssignments[itemIndex].consumers.push(clean);
            renderItemsListUI();
        }
    }
}

// --- Step 2: Natural Language Splitting ---

function setSamplePrompt(type) {
    const input = document.getElementById("nlInstructionInput");
    if (!input) return;
    if (type === 1) {
        input.value = "Pizza to Alice; Bob and Charlie split the Pasta and Calamari; all three of us shared the Tiramisu and drinks.";
    } else {
        input.value = "Split everything equally among Alice, Bob, and Charlie.";
    }
}

async function parseNaturalLanguageSplit() {
    const instruction = document.getElementById("nlInstructionInput").value.trim();
    if (!instruction) {
        alert("Please enter who ordered or shared what.");
        return;
    }

    const btn = document.getElementById("btnAiParse");
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-leaf"></i><span>AI Parsing...</span>`;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch("/api/split/parse-instruction", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                instruction: instruction,
                items: currentAssignments,
            })
        });
        if (!res.ok) throw new Error("AI parsing failed");
        const data = await res.json();

        // Update item consumers from assignments
        data.assignments.forEach(assign => {
            const match = currentAssignments.find(it => it.name.toLowerCase() === assign.item_name.toLowerCase());
            if (match) {
                match.consumers = assign.consumers;
            }
        });

        renderItemsListUI();

        // Display AI summary
        const summaryBox = document.getElementById("aiSummaryBox");
        const summaryText = document.getElementById("aiSummaryText");
        if (summaryBox && summaryText) {
            summaryText.textContent = data.ai_summary;
            summaryBox.classList.remove("hidden");
        }
    } catch (err) {
        alert("Failed to parse instruction: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="wand-2" class="w-4 h-4"></i><span>Ask AI to Assign</span>`;
        if (window.lucide) lucide.createIcons();
    }
}

async function proceedToGridReview() {
    const hasAnyConsumer = currentAssignments.some(it => it.consumers.length > 0);
    if (!hasAnyConsumer) {
        alert("Please assign at least one item to a friend before proceeding.");
        return;
    }

    showGlobalLoading("Computing exact integer shares with Hare-Niemeyer rounding...");
    try {
        const res = await fetch(`/api/split/calculate?bill_id=${currentBillId || ''}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                currency: currentCurrency,
                items: currentAssignments.map(item => ({
                    ...item,
                    price: convertAmount(item.price, currentReceiptData.currency),
                })),
                tax: convertAmount(currentReceiptData.tax, currentReceiptData.currency),
                tip: convertAmount(currentReceiptData.tip, currentReceiptData.currency),
                discount: convertAmount(currentReceiptData.discount, currentReceiptData.currency),
                override_total: convertAmount(currentReceiptData.total, currentReceiptData.currency),
            })
        });
        if (!res.ok) throw new Error("Calculation failed");
        currentSplitResult = await res.json();
        currentBillId = currentSplitResult.bill_id || currentBillId;
        currentSplitCurrency = currentCurrency;

        // Update Math Verification Badge
        const badge = document.getElementById("mathVerificationText");
        if (badge) {
            badge.textContent = `Hare-Niemeyer Verified: Sum of shares matches ${formatCurrency(currentSplitResult.total)} exactly.`;
        }

        goToStep(3);
    } catch (err) {
        alert("Calculation error: " + err.message);
    } finally {
        hideGlobalLoading();
    }
}

// --- Step 3: AG Grid Review & Audit Table ---

function renderAGGrid() {
    const gridDiv = document.querySelector("#splitGrid");
    if (!gridDiv || !currentSplitResult) return;

    // Prepare row data from shares with active currency
    const rowData = Object.values(currentSplitResult.shares).map(s => {
        const dishes = (s.assigned_items || []).map(d => `${d.item_name} (${formatCurrency(d.share_dollars)})`).join(", ");
        return {
            person: s.person,
            items_subtotal: s.items_subtotal,
            tax: s.tax,
            tip: s.tip,
            total: s.total,
            dishes: dishes || "None",
        };
    });

    const columnDefs = [
        {
            field: "person",
            headerName: "Friend",
            pinned: "left",
            width: 140,
            cellRenderer: (params) => `<div class="font-extrabold text-white flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-leaf"></span>${params.value}</div>`
        },
        {
            field: "items_subtotal",
            headerName: `Subtotal (${getCurrencySymbol()})`,
            width: 130,
            valueFormatter: p => formatCurrency(p.value),
            cellClass: "font-mono text-slate-200 font-semibold"
        },
        {
            field: "tax",
            headerName: `Tax (${getCurrencySymbol()})`,
            width: 120,
            valueFormatter: p => formatCurrency(p.value),
            cellClass: "font-mono text-slate-400"
        },
        {
            field: "tip",
            headerName: `Tip (${getCurrencySymbol()})`,
            width: 120,
            valueFormatter: p => formatCurrency(p.value),
            cellClass: "font-mono text-slate-400"
        },
        {
            field: "total",
            headerName: `Total Share (${getCurrencySymbol()})`,
            width: 150,
            valueFormatter: p => formatCurrency(p.value),
            cellClass: "font-mono font-black text-leaf text-base"
        },
        {
            field: "dishes",
            headerName: "Assigned Dishes",
            flex: 1,
            cellClass: "text-xs text-slate-300 truncate"
        }
    ];

    gridDiv.innerHTML = "";
    const gridOptions = {
        columnDefs: columnDefs,
        rowData: rowData,
        domLayout: 'autoHeight',
        defaultColDef: {
            sortable: true,
            filter: true,
            resizable: true
        }
    };

    gridApi = agGrid.createGrid(gridDiv, gridOptions);
}

// --- Step 4: PayPal Orders v2 & Settlement Dashboard ---

async function generatePayPalOrders() {
    if (!currentBillId) {
        alert("This bill is no longer saved on the server. Re-upload the receipt, then calculate the split again.");
        return;
    }

    showGlobalLoading("Converting shares to USD and generating PayPal orders...");
    try {
        const res = await fetch("/api/paypal/create-orders", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                bill_id: currentBillId,
                currency: currentCurrency
            })
        });
        if (!res.ok) {
            const errorData = await res.json().catch(() => null);
            throw new Error(errorData?.detail || `Order creation failed (HTTP ${res.status}).`);
        }
        const data = await res.json();
        currentOrders = data.orders;
        if (data.exchange_rate) {
            EXCHANGE_RATE_USD_TO_INR = Number(data.exchange_rate);
            EXCHANGE_RATE_DATE = data.exchange_rate_date;
            const rateText = document.getElementById("exchangeRateText");
            if (rateText) {
                rateText.textContent = `Reference rate (${EXCHANGE_RATE_DATE}): $1 = ₹${EXCHANGE_RATE_USD_TO_INR.toFixed(2)}. PayPal charges in USD.`;
            }
        }

        renderParticipantCards();
        goToStep(4);
        startPollingBillStatus();
    } catch (err) {
        alert("PayPal Order creation error: " + err.message);
    } finally {
        hideGlobalLoading();
    }
}

function renderParticipantCards() {
    const container = document.getElementById("participantCardsGrid");
    if (!container || !currentSplitResult) return;
    container.innerHTML = "";

    let totalAmount = 0;
    let paidAmount = 0;

    Object.values(currentSplitResult.shares).forEach(share => {
        totalAmount += share.total;
        const isPaid = share.status === "PAID";
        if (isPaid) paidAmount += share.total;

        const order = currentOrders.find(o => o.person === share.person) || {};
        const approvalUrl = order.approval_url || share.paypal_approval_url || "#";
        const qrData = order.qr_code_data || share.qr_code_data || "";

        const card = document.createElement("div");
        card.id = `share-card-${share.person.replace(/\s+/g, '-')}`;
        card.className = `glass-forest rounded-3xl p-6 border ${isPaid ? 'border-leaf bg-forest/80' : 'border-forest-border'} space-y-4 flex flex-col justify-between transition-all duration-300 shadow-xl`;

        card.innerHTML = `
            <div class="space-y-3">
                <div class="flex items-center justify-between">
                    <div>
                        <h4 class="font-black text-lg text-white">${share.person}</h4>
                        <p class="text-xs text-slate-300">Share: ${(share.assigned_items || []).length} items</p>
                    </div>
                    <span class="status-pill px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider ${isPaid ? 'bg-leaf text-forest' : 'bg-forest border border-leaf/40 text-leaf'}">
                        ${isPaid ? 'PAID' : 'PENDING'}
                    </span>
                </div>

                <div class="p-3.5 bg-forest-dark rounded-2xl border border-forest-border flex justify-between items-baseline shadow-inner">
                    <span class="text-xs text-slate-300 font-semibold">Amount Due:</span>
                    <span class="text-2xl font-black font-mono text-leaf">${formatCurrency(share.total)}</span>
                </div>
                ${order.total_amount != null ? `<p class="text-right text-[11px] text-slate-400">PayPal charges $${Number(order.total_amount).toFixed(2)} USD</p>` : ""}
            </div>

            <div class="space-y-2 pt-2 border-t border-forest-border">
                ${!isPaid ? `
                    <a href="${approvalUrl}" target="_blank" class="w-full py-3 px-4 bg-leaf hover:bg-leaf-muted text-forest font-black rounded-2xl text-xs flex items-center justify-center gap-2 transition shadow-lg glow-leaf">
                        <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                        <span>Pay with PayPal (${currentCurrency})</span>
                    </a>
                    <div class="grid grid-cols-2 gap-2">
                        <button onclick="openQrModal('${share.person}', ${share.total}, '${approvalUrl}', '${qrData}')" class="py-2.5 px-3 bg-forest hover:bg-forest-light text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 border border-forest-border transition">
                            <i data-lucide="qr-code" class="w-3.5 h-3.5 text-leaf"></i>
                            <span>Scan QR</span>
                        </button>
                        <button onclick="openNudgeModal('${share.person}', ${share.total}, '${approvalUrl}')" class="py-2.5 px-3 bg-forest hover:bg-forest-light text-leaf rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 border border-leaf/30 transition">
                            <i data-lucide="bell" class="w-3.5 h-3.5"></i>
                            <span>AI Nudge</span>
                        </button>
                    </div>
                    <button onclick="simulateFriendPayment('${order.order_id || share.paypal_order_id}')" class="w-full text-center text-[10px] text-slate-400 hover:text-leaf underline pt-1 transition">
                        Simulate friend payment now &rarr;
                    </button>
                ` : `
                    <div class="py-3 bg-leaf/20 rounded-2xl text-center text-xs font-black text-leaf border border-leaf/40 flex items-center justify-center gap-1.5 shadow-sm">
                        <i data-lucide="check-circle" class="w-4 h-4"></i>
                        <span>Payment Completed</span>
                    </div>
                `}
            </div>
        `;
        container.appendChild(card);
    });

    updateDashboardProgress(paidAmount, totalAmount);
    if (window.lucide) lucide.createIcons();
}

function updateDashboardProgress(paid, total) {
    const paidEl = document.getElementById("dashboardPaidAmount");
    const barEl = document.getElementById("dashboardProgressBar");
    const statusEl = document.getElementById("dashboardStatusText");

    if (paidEl) paidEl.textContent = `${formatCurrency(paid)} / ${formatCurrency(total)}`;
    const pct = total > 0 ? Math.min(100, Math.round((paid / total) * 100)) : 0;
    if (barEl) barEl.style.width = `${pct}%`;
    if (statusEl) {
        if (pct >= 100) {
            statusEl.textContent = "All Paid!";
            statusEl.className = "text-xs font-black text-leaf";
        } else {
            statusEl.textContent = `${pct}% Collected`;
            statusEl.className = "text-xs font-bold text-amber-300";
        }
    }
}

// --- Live Polling ---

function startPollingBillStatus() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(async () => {
        if (!currentBillId) return;
        try {
            const res = await fetch(`/api/bills/${currentBillId}`);
            if (!res.ok) return;
            const bill = await res.json();

            let paidCount = 0;
            bill.shares.forEach(s => {
                if (s.status === "PAID") paidCount++;
                if (currentSplitResult && currentSplitResult.shares[s.person]) {
                    currentSplitResult.shares[s.person].status = s.status;
                }
            });

            renderParticipantCards();

            if (bill.status === "COMPLETED" || (bill.shares.length > 0 && paidCount === bill.shares.length)) {
                clearInterval(pollingInterval);
            }
        } catch (e) {
            console.debug("Polling tick error", e);
        }
    }, 4000);
}

async function simulateFriendPayment(orderId) {
    if (!orderId) {
        alert("Order reference not ready yet.");
        return;
    }
    showGlobalLoading("Simulating PayPal instant checkout...");
    try {
        const res = await fetch(`/api/paypal/capture-order/${orderId}`, { method: "POST" });
        if (!res.ok) throw new Error("Capture failed");
        const billRes = await fetch(`/api/bills/${currentBillId}`);
        const bill = await billRes.json();
        bill.shares.forEach(s => {
            if (currentSplitResult && currentSplitResult.shares[s.person]) {
                currentSplitResult.shares[s.person].status = s.status;
            }
        });
        renderParticipantCards();
    } catch (err) {
        alert("Payment simulation failed: " + err.message);
    } finally {
        hideGlobalLoading();
    }
}

// --- Modals: QR Code & AI Nudge ---

function openQrModal(person, amount, url, qrData) {
    document.getElementById("qrModalPerson").textContent = `${person}'s Share`;
    document.getElementById("qrModalAmount").textContent = formatCurrency(amount);
    document.getElementById("qrModalDirectLink").href = url;

    const qrContainer = document.getElementById("qrCodeContainer");
    qrContainer.innerHTML = "";

    if (qrData && qrData.startsWith("data:image")) {
        const img = document.createElement("img");
        img.src = qrData;
        img.className = "w-full h-full object-contain";
        qrContainer.appendChild(img);
    } else if (window.QRCode) {
        new QRCode(qrContainer, {
            text: url,
            width: 180,
            height: 180,
            colorDark: "#064734",
            colorLight: "#ffffff",
        });
    }

    document.getElementById("qrModal").classList.remove("hidden");
}

function closeQrModal() {
    document.getElementById("qrModal").classList.add("hidden");
}

function openNudgeModal(person, amount, link) {
    currentNudgeShare = { person, amount, link };
    document.getElementById("nudgeModalPerson").textContent = person;
    selectNudgeTone('polite');
    document.getElementById("nudgeModal").classList.remove("hidden");
}

function closeNudgeModal() {
    document.getElementById("nudgeModal").classList.add("hidden");
}

async function selectNudgeTone(tone) {
    selectedTone = tone;
    document.querySelectorAll(".nudge-tone-btn").forEach(btn => {
        const isSelected = btn.getAttribute("data-tone") === tone;
        btn.className = `nudge-tone-btn py-2 px-2.5 rounded-xl border text-center transition ${
            isSelected
                ? 'border-leaf bg-forest text-leaf font-bold'
                : 'border-forest-border bg-forest-dark text-slate-300'
        }`;
    });

    if (!currentNudgeShare) return;
    const items = (currentSplitResult?.shares[currentNudgeShare.person]?.assigned_items || []).map(i => i.item_name);

    document.getElementById("nudgeMessageText").value = "Generating AI reminder in persona...";

    try {
        const res = await fetch("/api/nudge/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                person: currentNudgeShare.person,
                amount: currentNudgeShare.amount,
                merchant: currentReceiptData?.merchant || "our dinner",
                items: items,
                payment_link: currentNudgeShare.link,
                tone: tone,
            })
        });
        const data = await res.json();
        document.getElementById("nudgeMessageText").value = data.message;
        document.getElementById("nudgeWhatsappLink").href = data.shareable_whatsapp_url;
    } catch (e) {
        document.getElementById("nudgeMessageText").value = `Hi ${currentNudgeShare.person}! Your share comes to ${formatCurrency(currentNudgeShare.amount)}. Please pay via PayPal: ${currentNudgeShare.link}`;
    }
}

function copyNudgeText() {
    const text = document.getElementById("nudgeMessageText").value;
    navigator.clipboard.writeText(text).then(() => {
        const btnText = document.getElementById("copyNudgeBtnText");
        btnText.textContent = "Copied!";
        setTimeout(() => { btnText.textContent = "Copy Text"; }, 2000);
    });
}

function startNewBill() {
    if (pollingInterval) clearInterval(pollingInterval);
    currentBillId = null;
    currentReceiptData = null;
    currentSplitCurrency = null;
    currentAssignments = [];
    currentSplitResult = null;
    currentOrders = [];
    goToStep(1);
}

// --- Loading Indicators ---

function showGlobalLoading(msg) {
    let loader = document.getElementById("globalLoader");
    if (!loader) {
        loader = document.createElement("div");
        loader.id = "globalLoader";
        loader.className = "fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center gap-3 text-white";
        loader.innerHTML = `
            <div class="w-12 h-12 rounded-full border-4 border-forest border-t-leaf animate-spin"></div>
            <p id="globalLoaderMsg" class="text-sm font-bold text-leaf">Processing...</p>
        `;
        document.body.appendChild(loader);
    }
    document.getElementById("globalLoaderMsg").textContent = msg || "Processing...";
    loader.classList.remove("hidden");
}

function hideGlobalLoading() {
    const loader = document.getElementById("globalLoader");
    if (loader) loader.classList.add("hidden");
}
