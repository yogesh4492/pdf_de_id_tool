#!/usr/bin/env python3
"""Standalone Python FastAPI Web Application for PDF De-identification.

Provides an intuitive UI for uploading PDFs, customizing PII categories,
adding manual overrides, viewing statistics, and downloading redacted PDFs/text.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

# Try importing fitz (PyMuPDF) and handle error gracefully
try:
    import fitz
except ImportError:
    fitz = None

app = FastAPI(
    title="ShieldPDF De-identifier",
    description="De-identify PII from PDF documents in Python.",
    version="1.0.0"
)

# Reuse the redaction script's components dynamically by loading them
import sys
# Add parent directory to path so we can import redact
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    import redact
except ImportError:
    # If redact cannot be imported directly, we define placeholders
    redact = None

class RedactConfigSchema(BaseModel):
    manual_persons: Optional[List[str]] = None
    manual_companies: Optional[List[str]] = None
    manual_vehicles: Optional[List[str]] = None
    manual_bar_councils: Optional[List[str]] = None
    manual_emails: Optional[List[str]] = None
    manual_phones: Optional[List[str]] = None
    manual_cin_no: Optional[List[str]] = None
    manual_bars: Optional[List[str]] = None
    manual_cins: Optional[List[str]] = None
    manual_gsts: Optional[List[str]] = None
    manual_ifscs: Optional[List[str]] = None
    manual_accounts: Optional[List[str]] = None
    redact_categories: Optional[List[str]] = None

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the integrated modern HTML/Tailwind CSS user interface."""
    return """
<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-950">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShieldPDF — AI-Powered Document De-Identification</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
    </style>
</head>
<body class="h-full text-slate-100 flex flex-col">
    <!-- Navbar -->
    <header class="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="p-2 bg-indigo-600 rounded-lg text-white font-bold tracking-tight shadow-lg shadow-indigo-500/20">
                    🛡️
                </div>
                <div>
                    <h1 class="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-indigo-400">
                        ShieldPDF
                    </h1>
                    <p class="text-xs text-slate-400">Standalone Python De-identification Engine</p>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span class="w-1.5 h-1.5 bg-emerald-500 rounded-full mr-1.5 animate-pulse"></span>
                    Engine Ready
                </span>
            </div>
        </div>
    </header>

    <!-- Main Workspace -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 flex flex-col gap-6">
        <!-- Error Alert -->
        <div id="errorAlert" class="hidden bg-rose-500/10 border border-rose-500/20 text-rose-400 px-4 py-3 rounded-xl flex items-start space-x-3">
            <span class="text-xl">⚠️</span>
            <div class="flex-1">
                <h4 class="font-semibold text-sm">Operation Failed</h4>
                <p id="errorMessage" class="text-xs mt-0.5"></p>
            </div>
            <button onclick="hideError()" class="text-rose-400 hover:text-white">&times;</button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <!-- Left Side: Configs & Upload (4 cols) -->
            <div class="lg:col-span-4 flex flex-col gap-6">
                <!-- Upload Panel -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
                    <h3 class="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
                        <span>📁</span>
                        <span>Upload PDF Document</span>
                    </h3>
                    <div id="dropZone" class="border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-xl p-8 text-center cursor-pointer transition-all bg-slate-950/40">
                        <input type="file" id="fileInput" accept="application/pdf" class="hidden">
                        <div class="space-y-3">
                            <div class="text-4xl">📄</div>
                            <div>
                                <p class="text-sm font-medium text-slate-300">Drag & drop or <span class="text-indigo-400 hover:underline">browse</span></p>
                                <p class="text-xs text-slate-500 mt-1">PDF Files up to 25MB</p>
                            </div>
                        </div>
                    </div>
                    <div id="fileDetails" class="hidden mt-4 p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
                        <div class="flex items-center space-x-2.5 truncate">
                            <span class="text-xl text-indigo-400">📄</span>
                            <div class="truncate">
                                <p id="fileName" class="text-xs font-medium text-slate-200 truncate"></p>
                                <p id="fileSize" class="text-[10px] text-slate-500"></p>
                            </div>
                        </div>
                        <button onclick="resetFile()" class="text-slate-400 hover:text-rose-400 transition">&times;</button>
                    </div>
                </div>

                <!-- Custom Manual Overrides -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
                    <h3 class="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
                        <span>✏️</span>
                        <span>Manual Overrides</span>
                    </h3>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-xs font-medium text-slate-400 mb-1.5">Manual Names (Comma separated)</label>
                            <input type="text" id="manualPersons" placeholder="e.g. John Doe, Sarah Connor" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-400 mb-1.5">Manual Companies (Comma separated)</label>
                            <input type="text" id="manualCompanies" placeholder="e.g. Acme Corp, Initech" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-400 mb-1.5">Custom Dictionary Tags (Comma separated)</label>
                            <input type="text" id="manualBars" placeholder="e.g. SecretProject, TopConfidential" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                        </div>

                        <div class="pt-2">
                            <button
                                type="button"
                                id="toggleOverridesBtn"
                                onclick="toggleAllOverrides()"
                                class="w-full text-[10px] uppercase tracking-wider font-bold text-slate-400 py-2.5 border-t border-b border-dashed border-slate-800 flex items-center justify-between hover:text-white hover:border-slate-600 transition"
                            >
                                <span>Show All Tag-Specific Overrides</span>
                                <span class="text-xs">▼</span>
                            </button>
                        </div>

                        <div id="allOverridesContainer" class="hidden space-y-4 pt-2">
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual Vehicles</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[VEHICLE]</span>
                                </label>
                                <input type="text" id="manualVehicles" placeholder="e.g. DL-1C-AB-7234, MH-04-XYZ-1456" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual Phones</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[PHONE]</span>
                                </label>
                                <input type="text" id="manualPhones" placeholder="e.g. 9876543210, +91 99999 88888" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual Emails</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[EMAIL]</span>
                                </label>
                                <input type="text" id="manualEmails" placeholder="e.g. user@domain.com, contact@shaip.com" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual Bar Councils</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[BAR_COUNCIL]</span>
                                </label>
                                <input type="text" id="manualBarCouncils" placeholder="e.g. D/560/2009, IP/DEL/2014/0342" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual CIN Numbers</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[CIN]</span>
                                </label>
                                <input type="text" id="manualCins" placeholder="e.g. U72900DL2014PTC281355" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual GST Numbers</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[GST]</span>
                                </label>
                                <input type="text" id="manualGsts" placeholder="e.g. 07AAECP8388Q1Z5" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual IFSC Codes</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[IFSC]</span>
                                </label>
                                <input type="text" id="manualIfscs" placeholder="e.g. HDFC0001234, BARB0COLABA" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-400 mb-1.5 flex justify-between">
                                    <span>Manual Accounts</span>
                                    <span class="text-[10px] text-indigo-400 italic font-mono">[ACCOUNT]</span>
                                </label>
                                <input type="text" id="manualAccounts" placeholder="e.g. 50200012345678, 123456789" class="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                            </div>
                        </div>
                    </div>
                </div>

                <!-- PII Categories Selection -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
                    <h3 class="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
                        <span>⚙️</span>
                        <span>Redact Categories</span>
                    </h3>
                    <div class="grid grid-cols-2 gap-2.5" id="categoriesGrid">
                        <!-- Will be populated dynamically -->
                    </div>
                </div>

                <!-- Process Button -->
                <button id="processBtn" disabled onclick="processPDF()" class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium text-sm py-3 px-4 rounded-xl shadow-lg transition-all flex items-center justify-center space-x-2 cursor-pointer disabled:cursor-not-allowed">
                    <span>🛡️</span>
                    <span>De-identify PDF</span>
                </button>
            </div>

            <!-- Right Side: Workspace Results (8 cols) -->
            <div class="lg:col-span-8 flex flex-col gap-6">
                <!-- Welcome / Placeholder Screen -->
                <div id="placeholderScreen" class="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center shadow-xl flex flex-col items-center justify-center min-h-[500px]">
                    <div class="w-20 h-20 bg-indigo-600/10 rounded-full flex items-center justify-center text-4xl mb-6 border border-indigo-500/20 text-indigo-400">
                        🛡️
                    </div>
                    <h3 class="text-lg font-bold text-slate-200">De-Identify with Confidence</h3>
                    <p class="text-sm text-slate-400 mt-2 max-w-md mx-auto">
                        Upload a PDF document on the left, configure PII detection overrides, and hit "De-identify" to analyze and redact sensitive records in real-time.
                    </p>
                </div>

                <!-- Processing Loading Screen -->
                <div id="loadingScreen" class="hidden bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center shadow-xl flex flex-col items-center justify-center min-h-[500px]">
                    <div class="w-16 h-16 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-6"></div>
                    <h3 class="text-base font-bold text-slate-200">Processing Document...</h3>
                    <p class="text-xs text-slate-500 mt-2">Extracting content, resolving coordinates, and generating safe redacted file.</p>
                </div>

                <!-- Active Results Workspace -->
                <div id="resultsScreen" class="hidden flex flex-col gap-6">
                    <!-- Redaction Statistics Summary Banner -->
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4" id="statsGrid">
                        <!-- Stats cards injected here -->
                    </div>

                    <!-- PDF & Text Dual Workspace -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col">
                        <div class="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
                            <div class="flex space-x-2">
                                <button onclick="setTab('text')" id="tabBtnText" class="px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white transition">Extracted Text Preview</button>
                                <button onclick="setTab('entities')" id="tabBtnEntities" class="px-4 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-slate-200 transition">Detected Entities</button>
                            </div>
                            <div class="flex items-center space-x-2">
                                <button onclick="downloadText()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition">
                                    <span>💾</span>
                                    <span>Text</span>
                                </button>
                                <button onclick="downloadPDF()" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium flex items-center space-x-1.5 transition">
                                    <span>📥</span>
                                    <span>Redacted PDF</span>
                                </button>
                            </div>
                        </div>

                        <!-- Extracted Text Tab -->
                        <div id="tabContentText" class="grid grid-cols-1 md:grid-cols-2 gap-4 h-[450px]">
                            <div class="flex flex-col h-full bg-slate-950 border border-slate-800 rounded-xl p-4 overflow-hidden">
                                <h4 class="text-xs font-bold text-slate-400 mb-2.5 flex items-center justify-between">
                                    <span>ORIGINAL TEXT</span>
                                    <span class="text-[10px] text-indigo-400">READ-ONLY</span>
                                </h4>
                                <pre id="rawTextContainer" class="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed text-slate-300 select-text whitespace-pre-wrap pr-2"></pre>
                            </div>
                            <div class="flex flex-col h-full bg-slate-950 border border-slate-800 rounded-xl p-4 overflow-hidden">
                                <h4 class="text-xs font-bold text-slate-400 mb-2.5 flex items-center justify-between">
                                    <span>REDACTED PREVIEW</span>
                                    <span class="text-[10px] text-emerald-400">MASKED</span>
                                </h4>
                                <pre id="redactedTextContainer" class="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed text-emerald-300 select-text whitespace-pre-wrap pr-2"></pre>
                            </div>
                        </div>

                        <!-- Detected Entities Tab -->
                        <div id="tabContentEntities" class="hidden h-[450px] overflow-y-auto pr-2">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-3" id="entitiesContainer">
                                <!-- Cards injected here -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800 bg-slate-900/20 py-4 mt-auto">
        <div class="max-w-7xl mx-auto px-4 text-center">
            <p class="text-xs text-slate-500">ShieldPDF Standalone Service &bull; De-identification engine strictly compliant with security directives &bull; Runs completely on-premise.</p>
        </div>
    </footer>

    <script>
        const categories = {
            "person": { label: "Person Names", color: "bg-blue-500/10 text-blue-400 border-blue-500/20", tag: "[NAME]" },
            "company": { label: "Company Names", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", tag: "[COMPANY]" },
            "email": { label: "Emails", color: "bg-amber-500/10 text-amber-400 border-amber-500/20", tag: "[EMAIL]" },
            "phone": { label: "Phone Numbers", color: "bg-purple-500/10 text-purple-400 border-purple-500/20", tag: "[PHONE]" },
            "cin": { label: "CIN Numbers", color: "bg-rose-500/10 text-rose-400 border-rose-500/20", tag: "[CIN]" },
            "gst": { label: "GST Numbers", color: "bg-orange-500/10 text-orange-400 border-orange-500/20", tag: "[GST]" },
            "ifsc": { label: "IFSC Codes", color: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20", tag: "[IFSC]" },
            "account": { label: "Account Nos", color: "bg-violet-500/10 text-violet-400 border-violet-500/20", tag: "[ACCOUNT]" },
            "vehicle": { label: "Vehicle Plates", color: "bg-lime-500/10 text-lime-400 border-lime-500/20", tag: "[VEHICLE]" },
            "bar_council": { label: "Bar Councils", color: "bg-pink-500/10 text-pink-400 border-pink-500/20", tag: "[BAR_COUNCIL]" },
            "bar": { label: "Custom Tags", color: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20", tag: "[BAR]" }
        };

        let showAllOverrides = false;
        function toggleAllOverrides() {
            showAllOverrides = !showAllOverrides;
            const btn = document.getElementById("toggleOverridesBtn");
            const container = document.getElementById("allOverridesContainer");
            if (showAllOverrides) {
                container.classList.remove("hidden");
                btn.innerHTML = `<span>Hide All Tag-Specific Overrides</span><span class="text-xs">▲</span>`;
            } else {
                container.classList.add("hidden");
                btn.innerHTML = `<span>Show All Tag-Specific Overrides</span><span class="text-xs">▼</span>`;
            }
        }

        let selectedFile = null;
        let activeJobId = null;
        let activeResponseData = null;

        // Initialize Categories UI
        const grid = document.getElementById("categoriesGrid");
        Object.entries(categories).forEach(([key, value]) => {
            grid.innerHTML += `
                <label class="flex items-center space-x-2.5 p-2 bg-slate-950/40 border border-slate-800 rounded-lg hover:border-slate-700 cursor-pointer select-none">
                    <input type="checkbox" id="cat_${key}" checked value="${key}" class="rounded text-indigo-600 focus:ring-0 bg-slate-900 border-slate-800 w-4 h-4">
                    <span class="text-xs text-slate-300 font-medium">${value.label}</span>
                </label>
            `;
        });

        // Setup File Upload Interactions
        const dropZone = document.getElementById("dropZone");
        const fileInput = document.getElementById("fileInput");
        const fileDetails = document.getElementById("fileDetails");
        const fileName = document.getElementById("fileName");
        const fileSize = document.getElementById("fileSize");
        const processBtn = document.getElementById("processBtn");

        dropZone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => handleFile(e.target.files[0]);

        dropZone.ondragover = (e) => {
            e.preventDefault();
            dropZone.classList.add("border-indigo-500", "bg-indigo-500/5");
        };
        dropZone.ondragleave = () => {
            dropZone.classList.remove("border-indigo-500", "bg-indigo-500/5");
        };
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.classList.remove("border-indigo-500", "bg-indigo-500/5");
            handleFile(e.dataTransfer.files[0]);
        };

        function handleFile(file) {
            if (!file) return;
            if (file.type !== "application/pdf") {
                showError("Please upload a valid PDF document file.");
                return;
            }
            selectedFile = file;
            fileName.innerText = file.name;
            fileSize.innerText = (file.size / (1024 * 1024)).toFixed(2) + " MB";
            fileDetails.classList.remove("hidden");
            dropZone.classList.add("hidden");
            processBtn.removeAttribute("disabled");
            hideError();
        }

        function resetFile() {
            selectedFile = null;
            fileInput.value = "";
            fileDetails.classList.add("hidden");
            dropZone.classList.remove("hidden");
            processBtn.setAttribute("disabled", "true");
            document.getElementById("placeholderScreen").classList.remove("hidden");
            document.getElementById("resultsScreen").classList.add("hidden");
        }

        function setTab(tab) {
            const btnText = document.getElementById("tabBtnText");
            const btnEnt = document.getElementById("tabBtnEntities");
            const contentText = document.getElementById("tabContentText");
            const contentEnt = document.getElementById("tabContentEntities");

            if (tab === 'text') {
                btnText.className = "px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white transition";
                btnEnt.className = "px-4 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-slate-200 transition";
                contentText.classList.remove("hidden");
                contentEnt.classList.add("hidden");
            } else {
                btnEnt.className = "px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white transition";
                btnText.className = "px-4 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-slate-200 transition";
                contentEnt.classList.remove("hidden");
                contentText.classList.add("hidden");
            }
        }

        async function processPDF() {
            if (!selectedFile) return;

            document.getElementById("placeholderScreen").classList.add("hidden");
            document.getElementById("resultsScreen").classList.add("hidden");
            document.getElementById("loadingScreen").classList.remove("hidden");
            hideError();

            const formData = new FormData();
            formData.append("file", selectedFile);

            // Fetch list of active redaction categories
            const selectedCategories = [];
            Object.keys(categories).forEach(key => {
                if (document.getElementById(`cat_${key}`).checked) {
                    selectedCategories.push(key);
                }
            });

            const overrides = {
                manual_persons: document.getElementById("manualPersons").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_companies: document.getElementById("manualCompanies").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_bars: document.getElementById("manualBars").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_vehicles: document.getElementById("manualVehicles").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_phones: document.getElementById("manualPhones").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_emails: document.getElementById("manualEmails").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_bar_councils: document.getElementById("manualBarCouncils").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_cins: document.getElementById("manualCins").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_gsts: document.getElementById("manualGsts").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_ifscs: document.getElementById("manualIfscs").value.split(",").map(x => x.trim()).filter(Boolean),
                manual_accounts: document.getElementById("manualAccounts").value.split(",").map(x => x.trim()).filter(Boolean),
                redact_categories: selectedCategories
            };

            formData.append("config", JSON.stringify(overrides));

            try {
                const response = await fetch("/api/deidentify", {
                    method: "POST",
                    body: formData
                });
                const data = await response.json();

                if (data.status === "error") {
                    throw new Error(data.message);
                }

                activeResponseData = data;
                activeJobId = data.job_id;

                renderResults(data);
            } catch (err) {
                showError(err.message || "An error occurred during de-identification.");
                document.getElementById("placeholderScreen").classList.remove("hidden");
            } finally {
                document.getElementById("loadingScreen").classList.add("hidden");
            }
        }

        function renderResults(data) {
            document.getElementById("resultsScreen").classList.remove("hidden");

            // Stats grid
            const statsGrid = document.getElementById("statsGrid");
            statsGrid.innerHTML = "";
            let totalRedacted = 0;
            
            Object.entries(categories).forEach(([key, cat]) => {
                const count = data.counts[key] || 0;
                totalRedacted += count;
                statsGrid.innerHTML += `
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md flex flex-col justify-between">
                        <span class="text-[10px] uppercase tracking-wider text-slate-400 font-bold">${cat.label}</span>
                        <div class="flex items-baseline space-x-2 mt-2">
                            <span class="text-xl font-bold ${count > 0 ? 'text-indigo-400' : 'text-slate-500'}">${count}</span>
                            <span class="text-[10px] px-1.5 py-0.5 rounded ${cat.color}">${cat.tag}</span>
                        </div>
                    </div>
                `;
            });

            // Raw and redacted text containers
            document.getElementById("rawTextContainer").innerText = data.raw_text || "No text extracted.";
            document.getElementById("redactedTextContainer").innerText = data.redacted_text || "No text redacted.";

            // Unique entities tab
            const entContainer = document.getElementById("entitiesContainer");
            entContainer.innerHTML = "";
            if (!data.entities || data.entities.length === 0) {
                entContainer.innerHTML = `<div class="col-span-2 text-center text-slate-500 text-xs py-8">No specific entities detected or manual overrides provided.</div>`;
            } else {
                data.entities.forEach(ent => {
                    const catInfo = categories[ent.kind] || { label: ent.kind, color: "bg-slate-800 text-slate-400" };
                    entContainer.innerHTML += `
                        <div class="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between">
                            <span class="text-xs font-semibold text-slate-200 truncate select-all mr-2">${ent.value}</span>
                            <span class="text-[10px] font-bold px-2 py-0.5 rounded-md shrink-0 uppercase tracking-wider ${catInfo.color}">${catInfo.label}</span>
                        </div>
                    `;
                });
            }

            setTab("text");
        }

        function downloadPDF() {
            if (!activeJobId) return;
            window.open(`/api/download/${activeJobId}`, '_blank');
        }

        function downloadText() {
            if (!activeResponseData || !activeResponseData.redacted_text) return;
            const element = document.createElement("a");
            const file = new Blob([activeResponseData.redacted_text], {type: 'text/plain'});
            element.href = URL.createObjectURL(file);
            element.download = "de-identified-text.txt";
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        }

        function showError(msg) {
            document.getElementById("errorMessage").innerText = msg;
            document.getElementById("errorAlert").classList.remove("hidden");
        }

        function hideError() {
            document.getElementById("errorAlert").classList.add("hidden");
        }
    </script>
</body>
</html>
"""

# Local temporary folder managers
JOBS_STORE = tempfile.gettempdir()

@app.post("/api/deidentify")
async def deidentify(
    file: UploadFile = File(...),
    config: str = Form("{}")
):
    """Processes uploaded PDF file, runs redaction, and returns JSON metadata."""
    if not fitz:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "PyMuPDF (fitz) is not installed on this system."}
        )

    try:
        parsed_config = json.loads(config)
    except Exception:
        parsed_config = {}

    # Setup job directories
    job_id = os.urandom(8).hex()
    job_dir = Path(JOBS_STORE) / f"shieldpdf_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)

    input_pdf_path = job_dir / "input.pdf"
    output_pdf_path = job_dir / "redacted.pdf"

    # Save uploaded file
    with open(input_pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Run redaction using imported redact module
        if not redact:
            raise HTTPException(status_code=500, detail="Redaction core module is not loaded correctly.")
        
        counters, entities, raw_text, redacted_text = redact.redact_pdf(
            input_pdf_path, 
            output_pdf_path, 
            parsed_config
        )

        return {
            "status": "success",
            "job_id": job_id,
            "counts": dict(counters),
            "entities": entities,
            "raw_text": raw_text[:50000],
            "redacted_text": redacted_text[:50000]
        }

    except Exception as e:
        # Cleanup in case of error
        shutil.rmtree(job_dir, ignore_errors=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Processing failed: {str(e)}"}
        )

@app.get("/api/download/{job_id}")
async def download_file(job_id: str):
    """Downloads the redacted PDF file by job_id."""
    target_path = Path(JOBS_STORE) / f"shieldpdf_{job_id}" / "redacted.pdf"
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found or session expired.")
    return FileResponse(
        target_path, 
        media_type="application/pdf", 
        filename="de-identified_document.pdf"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
