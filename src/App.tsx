import React, { useState, useRef } from "react";
import { 
  Shield, 
  FileText, 
  UploadCloud, 
  Settings, 
  CheckSquare, 
  Square, 
  Plus, 
  Download, 
  FileCode, 
  Eye, 
  EyeOff, 
  ListFilter, 
  RefreshCw, 
  AlertTriangle, 
  X,
  FileSpreadsheet,
  Globe,
  Tag
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

// Categorized definitions for styling
interface CategoryConfig {
  label: string;
  color: string;
  textColor: string;
  borderColor: string;
  bgLight: string;
  tag: string;
}

const CATEGORIES: Record<string, CategoryConfig> = {
  person: { 
    label: "Person Names", 
    color: "bg-blue-600", 
    textColor: "text-blue-800", 
    borderColor: "border-blue-300", 
    bgLight: "bg-blue-50",
    tag: "[NAME]" 
  },
  company: { 
    label: "Companies", 
    color: "bg-emerald-600", 
    textColor: "text-emerald-800", 
    borderColor: "border-emerald-300", 
    bgLight: "bg-emerald-50",
    tag: "[COMPANY]" 
  },
  email: { 
    label: "Emails", 
    color: "bg-amber-600", 
    textColor: "text-amber-800", 
    borderColor: "border-amber-300", 
    bgLight: "bg-amber-50",
    tag: "[EMAIL]" 
  },
  phone: { 
    label: "Phone Numbers", 
    color: "bg-purple-600", 
    textColor: "text-purple-800", 
    borderColor: "border-purple-300", 
    bgLight: "bg-purple-50",
    tag: "[PHONE]" 
  },
  cin: { 
    label: "CIN Numbers", 
    color: "bg-rose-600", 
    textColor: "text-rose-800", 
    borderColor: "border-rose-300", 
    bgLight: "bg-rose-50",
    tag: "[CIN]" 
  },
  gst: { 
    label: "GST Numbers", 
    color: "bg-orange-600", 
    textColor: "text-orange-800", 
    borderColor: "border-orange-300", 
    bgLight: "bg-orange-50",
    tag: "[GST]" 
  },
  ifsc: { 
    label: "IFSC Codes", 
    color: "bg-cyan-600", 
    textColor: "text-cyan-800", 
    borderColor: "border-cyan-300", 
    bgLight: "bg-cyan-50",
    tag: "[IFSC]" 
  },
  account: { 
    label: "Account Nos", 
    color: "bg-violet-600", 
    textColor: "text-violet-800", 
    borderColor: "border-violet-300", 
    bgLight: "bg-violet-50",
    tag: "[ACCOUNT]" 
  },
  vehicle: { 
    label: "Vehicle Plates", 
    color: "bg-lime-600", 
    textColor: "text-lime-800", 
    borderColor: "border-lime-300", 
    bgLight: "bg-lime-50",
    tag: "[VEHICLE]" 
  },
  bar_council: { 
    label: "Bar Councils", 
    color: "bg-pink-600", 
    textColor: "text-pink-800", 
    borderColor: "border-pink-300", 
    bgLight: "bg-pink-50",
    tag: "[BAR_COUNCIL]" 
  },
  bar: { 
    label: "Custom Tags", 
    color: "bg-yellow-600", 
    textColor: "text-yellow-800", 
    borderColor: "border-yellow-300", 
    bgLight: "bg-yellow-50",
    tag: "[BAR]" 
  }
};

interface ExtractedEntity {
  value: string;
  kind: string;
}

interface RedactResponse {
  status: string;
  counts: Record<string, number>;
  entities: ExtractedEntity[];
  raw_text: string;
  redacted_text: string;
  job_id: string;
  message?: string;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RedactResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"text" | "entities" | "export">("text");

  // Dynamic config options
  const [selectedCategories, setSelectedCategories] = useState<string[]>(Object.keys(CATEGORIES));
  const [showAllOverrides, setShowAllOverrides] = useState(false);
  const [manualPersons, setManualPersons] = useState<string>("");
  const [manualCompanies, setManualCompanies] = useState<string>("");
  const [manualVehicles, setManualVehicles] = useState<string>("");
  const [manualPhones, setManualPhones] = useState<string>("");
  const [manualEmails, setManualEmails] = useState<string>("");
  const [manualBarCouncils, setManualBarCouncils] = useState<string>("");
  const [manualCins, setManualCins] = useState<string>("");
  const [manualGsts, setManualGsts] = useState<string>("");
  const [manualIfscs, setManualIfscs] = useState<string>("");
  const [manualAccounts, setManualAccounts] = useState<string>("");
  const [manualBars, setManualBars] = useState<string>("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === "application/pdf") {
      setFile(droppedFile);
      setError(null);
    } else {
      setError("Please upload a valid PDF document file.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected && selected.type === "application/pdf") {
      setFile(selected);
      setError(null);
    } else {
      setError("Please upload a valid PDF document file.");
    }
  };

  const resetState = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const toggleCategory = (cat: string) => {
    setSelectedCategories(prev => 
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  };

  const handleDeidentify = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    const overrides = {
      manual_persons: manualPersons.split(",").map(x => x.trim()).filter(Boolean),
      manual_companies: manualCompanies.split(",").map(x => x.trim()).filter(Boolean),
      manual_vehicles: manualVehicles.split(",").map(x => x.trim()).filter(Boolean),
      manual_phones: manualPhones.split(",").map(x => x.trim()).filter(Boolean),
      manual_emails: manualEmails.split(",").map(x => x.trim()).filter(Boolean),
      manual_bar_councils: manualBarCouncils.split(",").map(x => x.trim()).filter(Boolean),
      manual_cins: manualCins.split(",").map(x => x.trim()).filter(Boolean),
      manual_gsts: manualGsts.split(",").map(x => x.trim()).filter(Boolean),
      manual_ifscs: manualIfscs.split(",").map(x => x.trim()).filter(Boolean),
      manual_accounts: manualAccounts.split(",").map(x => x.trim()).filter(Boolean),
      manual_bars: manualBars.split(",").map(x => x.trim()).filter(Boolean),
      redact_categories: selectedCategories
    };

    formData.append("config", JSON.stringify(overrides));

    try {
      const response = await fetch("/api/deidentify", {
        method: "POST",
        body: formData,
      });

      const data: RedactResponse = await response.json();

      if (data.status === "error") {
        throw new Error(data.message || "An error occurred during redaction.");
      }

      setResult(data);
      setActiveTab("text");
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred while communicating with the server.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = () => {
    if (!result?.job_id) return;
    window.open(`/api/download/${result.job_id}`, "_blank");
  };

  const handleDownloadText = () => {
    if (!result?.redacted_text) return;
    const element = document.createElement("a");
    const blob = new Blob([result.redacted_text], { type: "text/plain;charset=utf-8" });
    element.href = URL.createObjectURL(blob);
    element.download = "de-identified-document.txt";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const totalRedactions = result 
    ? Object.values(result.counts).reduce((a: number, b) => a + (b as number), 0)
    : 0;

  return (
    <div id="app" className="min-h-screen bg-[#F9F8F6] text-[#1A1A1A] font-sans flex flex-col selection:bg-[#1A1A1A] selection:text-white">
      
      {/* Top Banner Header */}
      <header id="header" className="border-b-2 border-[#1A1A1A] bg-[#F9F8F6] sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="p-2.5 bg-[#1A1A1A] text-white border border-[#1A1A1A] shadow-[2px_2px_0px_0px_#ECEBE8]">
              <Shield className="w-6 h-6" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-3xl font-serif italic font-black tracking-tighter leading-none text-[#1A1A1A]">
                ShieldPDF
              </h1>
              <p className="text-[10px] uppercase tracking-[0.3em] font-bold opacity-60 text-[#1A1A1A] mt-0.5">
                Privacy-First PDF De-Identification
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="inline-flex items-center px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest bg-[#1A1A1A] text-white border border-[#1A1A1A]">
              On-Premise Engine
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main id="main" className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 flex flex-col gap-6">
        
        {/* Error Notification Alert */}
        <AnimatePresence>
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="bg-red-50 border-2 border-red-600 text-red-900 px-4 py-3.5 flex items-start space-x-3 shadow-[4px_4px_0px_0px_#1A1A1A]"
            >
              <AlertTriangle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" />
              <div className="flex-1">
                <h4 className="font-bold text-xs uppercase tracking-widest text-red-800">Processing Failed</h4>
                <p className="text-xs text-red-900 mt-0.5 font-medium">{error}</p>
              </div>
              <button onClick={() => setError(null)} className="text-red-600 hover:text-red-950 shrink-0">
                <X className="w-4 h-4" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Left Column: upload panel, configs, manual overrides (4 cols) */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            
            {/* Upload Box Card */}
            <div id="uploadCard" className="bg-white border-2 border-[#1A1A1A] p-6 shadow-[6px_6px_0px_0px_#1A1A1A] relative overflow-hidden group">
              <h3 className="text-xs font-bold text-[#1A1A1A] uppercase tracking-widest border-b border-[#1A1A1A]/20 pb-2.5 mb-4 flex items-center space-x-2">
                <FileText className="w-4 h-4 text-[#1A1A1A]" />
                <span>Source Document</span>
              </h3>

              {!file ? (
                <div 
                  id="dropZone"
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed p-8 text-center cursor-pointer transition-all duration-300 ${
                    isDragging 
                      ? "border-[#1A1A1A] bg-amber-50/40" 
                      : "border-gray-300 hover:border-[#1A1A1A] bg-[#F9F8F6]/50"
                  }`}
                >
                  <input 
                    type="file" 
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept="application/pdf" 
                    className="hidden" 
                  />
                  <div className="space-y-4">
                    <div className="w-12 h-12 bg-white border-2 border-[#1A1A1A] flex items-center justify-center mx-auto text-[#1A1A1A] group-hover:bg-[#1A1A1A] group-hover:text-white transition-colors duration-350">
                      <UploadCloud className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#1A1A1A] uppercase tracking-wider">Drag & drop your PDF here, or <span className="underline cursor-pointer">browse</span></p>
                      <p className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold mt-2.5">Accepts PDF documents up to 25MB</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div id="fileStatus" className="flex items-center justify-between p-3.5 bg-[#F9F8F6] border border-[#1A1A1A]">
                  <div className="flex items-center space-x-3 truncate">
                    <div className="p-2 bg-[#1A1A1A] text-white">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="truncate">
                      <p className="text-xs font-bold text-[#1A1A1A] truncate">{file.name}</p>
                      <p className="text-[10px] font-mono text-gray-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                  </div>
                  <button 
                    onClick={resetState} 
                    className="p-1.5 hover:bg-gray-200 text-[#1A1A1A] hover:text-red-600 transition"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>

            {/* Manual Overrides Form Panel */}
            <div id="overridesCard" className="bg-white border-2 border-[#1A1A1A] p-6 shadow-[6px_6px_0px_0px_#1A1A1A]">
              <h3 className="text-xs font-bold text-[#1A1A1A] uppercase tracking-widest border-b border-[#1A1A1A]/20 pb-2.5 mb-4 flex items-center space-x-2">
                <Settings className="w-4 h-4 text-[#1A1A1A]" />
                <span>Manual Overrides</span>
              </h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                    <span>Manual Names dictionary</span>
                    <span className="text-[9px] lowercase font-normal italic text-gray-400">Comma separated</span>
                  </label>
                  <input 
                    type="text" 
                    value={manualPersons}
                    onChange={(e) => setManualPersons(e.target.value)}
                    placeholder="e.g. Akash Verma, Mr. Upadhyay"
                    className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                    <span>Manual Companies dictionary</span>
                    <span className="text-[9px] lowercase font-normal italic text-gray-400">Comma separated</span>
                  </label>
                  <input 
                    type="text" 
                    value={manualCompanies}
                    onChange={(e) => setManualCompanies(e.target.value)}
                    placeholder="e.g. Khaitan & Co, Yebhi AI"
                    className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                    <span>Custom Dictionary Words</span>
                    <span className="text-[9px] text-[#1A1A1A]/60 lowercase italic">Redacted with [BAR] tag</span>
                  </label>
                  <input 
                    type="text" 
                    value={manualBars}
                    onChange={(e) => setManualBars(e.target.value)}
                    placeholder="e.g. Milky Way, Snickers"
                    className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAllOverrides(!showAllOverrides)}
                    className="w-full text-[10px] uppercase tracking-wider font-bold text-gray-500 py-2.5 border-t border-b border-dashed border-gray-300 flex items-center justify-between hover:text-[#1A1A1A] hover:border-[#1A1A1A] transition"
                  >
                    <span>{showAllOverrides ? "Hide" : "Show"} All Tag-Specific Overrides</span>
                    <span className="text-xs">{showAllOverrides ? "▲" : "▼"}</span>
                  </button>
                </div>

                {showAllOverrides && (
                  <div className="space-y-4 pt-2 animate-fadeIn">
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual Vehicles</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[VEHICLE]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualVehicles}
                        onChange={(e) => setManualVehicles(e.target.value)}
                        placeholder="e.g. DL-1C-AB-7234, MH-04-XYZ-1456"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual Phones</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[PHONE]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualPhones}
                        onChange={(e) => setManualPhones(e.target.value)}
                        placeholder="e.g. 9876543210, +91 99999 88888"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual Emails</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[EMAIL]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualEmails}
                        onChange={(e) => setManualEmails(e.target.value)}
                        placeholder="e.g. user@domain.com, contact@shaip.com"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual Bar Councils</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[BAR_COUNCIL]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualBarCouncils}
                        onChange={(e) => setManualBarCouncils(e.target.value)}
                        placeholder="e.g. D/560/2009, IP/DEL/2014/0342"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual CIN Numbers</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[CIN]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualCins}
                        onChange={(e) => setManualCins(e.target.value)}
                        placeholder="e.g. U72900DL2014PTC281355"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual GST Numbers</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[GST]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualGsts}
                        onChange={(e) => setManualGsts(e.target.value)}
                        placeholder="e.g. 07AAECP8388Q1Z5"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual IFSC Codes</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[IFSC]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualIfscs}
                        onChange={(e) => setManualIfscs(e.target.value)}
                        placeholder="e.g. HDFC0001234, BARB0COLABA"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest font-bold text-gray-500 mb-1.5 flex justify-between">
                        <span>Manual Accounts</span>
                        <span className="text-[9px] text-[#1A1A1A]/60 italic font-mono">[ACCOUNT]</span>
                      </label>
                      <input 
                        type="text" 
                        value={manualAccounts}
                        onChange={(e) => setManualAccounts(e.target.value)}
                        placeholder="e.g. 50200012345678, 123456789"
                        className="w-full text-xs bg-white border border-[#1A1A1A] px-3.5 py-2.5 text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-b-2 transition-all font-medium"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Redact Categories Multi-select */}
            <div id="categoriesCard" className="bg-white border-2 border-[#1A1A1A] p-6 shadow-[6px_6px_0px_0px_#1A1A1A]">
              <h3 className="text-xs font-bold text-[#1A1A1A] uppercase tracking-widest border-b border-[#1A1A1A]/20 pb-2.5 mb-4 flex items-center space-x-2">
                <ListFilter className="w-4 h-4 text-[#1A1A1A]" />
                <span>Detection Filters</span>
              </h3>
              
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(CATEGORIES).map(([key, cat]) => {
                  const isChecked = selectedCategories.includes(key);
                  return (
                    <button 
                      key={key}
                      onClick={() => toggleCategory(key)}
                      className={`flex items-center space-x-2.5 p-2 rounded-none border text-left transition duration-150 ${
                        isChecked 
                          ? "bg-[#1A1A1A] border-[#1A1A1A] text-white font-semibold" 
                          : "bg-transparent border-[#1A1A1A]/20 text-gray-500 hover:border-[#1A1A1A] hover:text-[#1A1A1A]"
                      }`}
                    >
                      {isChecked ? (
                        <CheckSquare className="w-4 h-4 shrink-0 text-white" />
                      ) : (
                        <Square className="w-4 h-4 shrink-0" />
                      )}
                      <span className="text-[11px] font-bold uppercase tracking-wider truncate">{cat.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* CTA action trigger button */}
            <button 
              id="actionBtn"
              disabled={!file || loading}
              onClick={handleDeidentify}
              className="w-full bg-[#1A1A1A] hover:bg-[#F9F8F6] hover:text-[#1A1A1A] text-white font-bold text-xs uppercase tracking-widest py-4 px-4 border-2 border-[#1A1A1A] shadow-[6px_6px_0px_0px_#ECEBE8] hover:shadow-none transition-all duration-200 flex items-center justify-center space-x-2.5 cursor-pointer disabled:bg-gray-100 disabled:text-gray-400 disabled:border-gray-200 disabled:shadow-none disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Processing Document...</span>
                </>
              ) : (
                <>
                  <Shield className="w-4 h-4" />
                  <span>De-identify Document</span>
                </>
              )}
            </button>

          </div>

          {/* Right Column: Loading state, welcome card, interactive workspace (8 cols) */}
          <div className="lg:col-span-8 flex flex-col gap-6">
            
            {/* 1. Placeholder screen */}
            {!file && !loading && !result && (
              <div id="placeholder" className="bg-white border-2 border-[#1A1A1A] p-12 text-center shadow-[10px_10px_0px_0px_#1A1A1A] flex flex-col items-center justify-center min-h-[550px]">
                <div className="w-20 h-20 bg-[#F9F8F6] border border-[#1A1A1A] flex items-center justify-center text-4xl mb-6 shadow-[4px_4px_0px_0px_#1A1A1A]">
                  🛡️
                </div>
                <h3 className="text-2xl font-serif italic font-black text-[#1A1A1A]">De-Identify with ShieldPDF</h3>
                <p className="text-xs text-gray-600 mt-3.5 max-w-sm mx-auto leading-relaxed">
                  Protect and redact sensitive records from legal, financial, or custom PDF documents. Cleanly removes names, accounts, plate numbers, and dynamic patterns instantly on-premise.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-lg w-full mt-12 text-left">
                  <div className="p-5 bg-[#F9F8F6] border border-[#1A1A1A]">
                    <span className="text-2xl font-serif italic font-black">01 /</span>
                    <h5 className="text-xs font-bold uppercase tracking-wider text-[#1A1A1A] mt-2">Upload Files Safely</h5>
                    <p className="text-[11px] text-gray-600 mt-1.5 leading-relaxed">Files are processed instantly on secure server nodes, keeping your private data completely isolated.</p>
                  </div>
                  <div className="p-5 bg-[#F9F8F6] border border-[#1A1A1A]">
                    <span className="text-2xl font-serif italic font-black">02 /</span>
                    <h5 className="text-xs font-bold uppercase tracking-wider text-[#1A1A1A] mt-2">Custom Redactions</h5>
                    <p className="text-[11px] text-gray-600 mt-1.5 leading-relaxed">Toggle filters or define exact keyword dictionaries to mask proprietary details on-the-fly.</p>
                  </div>
                </div>
              </div>
            )}

            {/* 2. Loading state container */}
            {loading && (
              <div id="loading" className="bg-white border-2 border-[#1A1A1A] p-12 text-center shadow-[10px_10px_0px_0px_#1A1A1A] flex flex-col items-center justify-center min-h-[550px]">
                <div className="relative">
                  <div className="w-16 h-16 border-4 border-[#1A1A1A] border-t-transparent rounded-full animate-spin"></div>
                  <Shield className="w-6 h-6 text-[#1A1A1A] absolute inset-0 m-auto animate-pulse" />
                </div>
                <h3 className="text-lg font-serif italic font-black text-[#1A1A1A] mt-8">De-identifying PDF Document...</h3>
                <p className="text-xs text-gray-500 mt-2.5 max-w-xs mx-auto leading-relaxed">
                  Analyzing document patterns, running manual override dictionaries, and generating coordinates to apply layout-preserving redactions.
                </p>
              </div>
            )}

            {/* 3. Success Results Workspace */}
            {result && !loading && (
              <div id="results" className="flex flex-col gap-6">
                
                {/* Statistics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-white border-2 border-[#1A1A1A] p-4 shadow-[6px_6px_0px_0px_#1A1A1A] flex flex-col justify-between">
                    <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Total Redactions</span>
                    <span className="text-3xl font-serif italic font-black text-[#1A1A1A] mt-1.5">{totalRedactions}</span>
                  </div>
                  <div className="bg-white border-2 border-[#1A1A1A] p-4 shadow-[6px_6px_0px_0px_#1A1A1A] flex flex-col justify-between">
                    <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Names Masked</span>
                    <span className="text-3xl font-serif italic font-black text-blue-800 mt-1.5">{result.counts.person || 0}</span>
                  </div>
                  <div className="bg-white border-2 border-[#1A1A1A] p-4 shadow-[6px_6px_0px_0px_#1A1A1A] flex flex-col justify-between">
                    <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Companies Masked</span>
                    <span className="text-3xl font-serif italic font-black text-emerald-800 mt-1.5">{result.counts.company || 0}</span>
                  </div>
                  <div className="bg-white border-2 border-[#1A1A1A] p-4 shadow-[6px_6px_0px_0px_#1A1A1A] flex flex-col justify-between">
                    <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Financial & CIN</span>
                    <span className="text-3xl font-serif italic font-black text-rose-800 mt-1.5">
                      {(result.counts.cin || 0) + (result.counts.gst || 0) + (result.counts.account || 0)}
                    </span>
                  </div>
                </div>

                {/* Primary Interactive View Workspace */}
                <div className="bg-white border-2 border-[#1A1A1A] p-6 shadow-[10px_10px_0px_0px_#1A1A1A] flex flex-col relative">
                  
                  {/* Floating Tag similar to the layout in design */}
                  <div className="absolute -top-3.5 -left-3.5 bg-[#1A1A1A] text-white text-[9px] font-bold px-3.5 py-1 uppercase tracking-widest border border-white shadow-[2px_2px_0px_0px_rgba(0,0,0,0.15)]">
                    Preview: output_scrubbed.pdf
                  </div>

                  {/* Tab bar header */}
                  <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#1A1A1A]/20 pb-4 mb-4 mt-2 gap-4">
                    <div className="flex space-x-1.5 bg-[#F9F8F6] p-1 border border-[#1A1A1A]">
                      <button 
                        onClick={() => setActiveTab("text")}
                        className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider transition ${
                          activeTab === "text" 
                            ? "bg-[#1A1A1A] text-white shadow-none" 
                            : "text-gray-600 hover:text-[#1A1A1A]"
                        }`}
                      >
                        Side-by-Side Preview
                      </button>
                      <button 
                        onClick={() => setActiveTab("entities")}
                        className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider transition ${
                          activeTab === "entities" 
                            ? "bg-[#1A1A1A] text-white shadow-none" 
                            : "text-gray-600 hover:text-[#1A1A1A]"
                        }`}
                      >
                        Identified Entities ({result.entities?.length || 0})
                      </button>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <button 
                        onClick={handleDownloadText}
                        className="px-4 py-2 bg-transparent hover:bg-gray-100 border border-[#1A1A1A] text-[#1A1A1A] text-[10px] font-bold uppercase tracking-widest flex items-center space-x-2 transition"
                      >
                        <FileCode className="w-3.5 h-3.5" />
                        <span>Download Text</span>
                      </button>
                      <button 
                        onClick={handleDownloadPDF}
                        className="px-4 py-2 bg-[#1A1A1A] hover:bg-white hover:text-[#1A1A1A] border border-[#1A1A1A] text-white text-[10px] font-bold uppercase tracking-widest flex items-center space-x-2 transition"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Redacted PDF</span>
                      </button>
                    </div>
                  </div>

                  {/* TAB CONTENT: Side-by-Side Preview */}
                  {activeTab === "text" && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-[480px]">
                      
                      {/* Left: Raw text */}
                      <div className="flex flex-col h-full bg-[#F9F8F6] border border-[#1A1A1A]/40 p-4 overflow-hidden">
                        <div className="flex items-center justify-between border-b border-[#1A1A1A]/20 pb-2 mb-2">
                          <span className="text-[9px] uppercase font-bold text-gray-500 tracking-widest">Original Text Content</span>
                          <span className="text-[9px] font-bold uppercase tracking-widest opacity-40">READ-ONLY</span>
                        </div>
                        <pre className="flex-1 overflow-y-auto font-serif text-[13px] leading-relaxed text-[#444444] whitespace-pre-wrap pr-2 select-text scrollbar-thin">
                          {result.raw_text || "No text could be extracted."}
                        </pre>
                      </div>

                      {/* Right: Redacted Preview */}
                      <div className="flex flex-col h-full bg-white border border-[#1A1A1A] p-4 overflow-hidden">
                        <div className="flex items-center justify-between border-b border-[#1A1A1A]/20 pb-2 mb-2">
                          <span className="text-[9px] uppercase font-bold text-red-600 tracking-widest flex items-center">
                            <span className="w-1.5 h-1.5 bg-red-600 rounded-full mr-1.5 animate-pulse"></span>
                            Redacted Output Preview
                          </span>
                          <span className="text-[9px] text-red-600 font-bold uppercase tracking-widest">PROTECTED</span>
                        </div>
                        <pre className="flex-1 overflow-y-auto font-serif text-[13px] leading-relaxed text-[#1A1A1A] whitespace-pre-wrap pr-2 select-text scrollbar-thin">
                          {result.redacted_text || "No text available."}
                        </pre>
                      </div>

                    </div>
                  )}

                  {/* TAB CONTENT: Identified Entities */}
                  {activeTab === "entities" && (
                    <div className="h-[480px] overflow-y-auto pr-2 scrollbar-thin">
                      {!result.entities || result.entities.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-gray-500 text-xs">
                          <AlertTriangle className="w-8 h-8 text-gray-400 mb-2" />
                          <span className="uppercase tracking-widest font-bold text-[10px]">No PII entities were parsed</span>
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {result.entities.map((ent, idx) => {
                            const catStyle = CATEGORIES[ent.kind] || { 
                              label: ent.kind, 
                              color: "bg-gray-800", 
                              textColor: "text-gray-900", 
                              borderColor: "border-gray-400", 
                              bgLight: "bg-gray-100" 
                            };
                            return (
                              <div 
                                key={idx}
                                className="bg-[#F9F8F6] border border-[#1A1A1A] p-3.5 flex items-center justify-between shadow-[2px_2px_0px_0px_#1A1A1A]"
                              >
                                <div className="truncate pr-4">
                                  <span className="text-xs font-bold text-[#1A1A1A] select-all tracking-wide truncate block">{ent.value}</span>
                                </div>
                                <span className={`text-[9px] uppercase font-bold px-2 py-0.5 border-2 tracking-wider shrink-0 select-none ${catStyle.textColor} ${catStyle.borderColor} ${catStyle.bgLight}`}>
                                  {catStyle.label}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}

                </div>

              </div>
            )}

          </div>

        </div>

      </main>

      {/* Footer copyright */}
      <footer id="footer" className="border-t-2 border-[#1A1A1A] bg-[#1A1A1A] text-white py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center space-y-2">
          <p className="text-[10px] text-gray-400 uppercase tracking-[0.2em] font-semibold leading-relaxed">
            ShieldPDF Document Sanitization Standard &bull; Runs under secure on-premise cloud containment &bull; Full-stack architecture powered by React, Express, and dynamic PyMuPDF redaction hooks.
          </p>
          <p className="text-[9px] text-gray-500 uppercase tracking-[0.15em] font-medium">
            © 2026 ShieldPDF Data Privacy Tools. All Rights Reserved.
          </p>
        </div>
      </footer>

    </div>
  );
}
