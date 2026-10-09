"use client";

import Image from "next/image";
import { useState, useRef, useCallback } from "react";
import { Upload, FileText, AlertCircle, CheckCircle2, X, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

interface SetupFormProps {
  onAnalysisStarted: (analysisId: string) => void;
}

export function SetupForm({ onAnalysisStarted }: SetupFormProps) {
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [supplierJson, setSupplierJson] = useState<string>("");
  const [supplierError, setSupplierError] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string>("");
  const pdfInputRef = useRef<HTMLInputElement>(null);
  const jsonInputRef = useRef<HTMLInputElement>(null);

  const handlePdfDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(
      (f) => f.type === "application/pdf"
    );
    if (files.length === 0) return;
    setPdfFiles((prev) => {
      const combined = [...prev, ...files];
      return combined.slice(0, 10);
    });
  }, []);

  const handlePdfChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setPdfFiles((prev) => [...prev, ...files].slice(0, 10));
    e.target.value = "";
  };

  const removeFile = (idx: number) =>
    setPdfFiles((prev) => prev.filter((_, i) => i !== idx));

  const handleJsonFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setSupplierJson(text);
      validateJson(text);
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const validateJson = (text: string): boolean => {
    try {
      JSON.parse(text);
      setSupplierError("");
      return true;
    } catch {
      setSupplierError("Invalid JSON — please check the format.");
      return false;
    }
  };

  const handleSubmit = async () => {
    if (pdfFiles.length === 0) {
      setError("Upload at least one PDF tender document.");
      return;
    }
    if (!supplierJson) {
      setError("Provide a supplier profile JSON.");
      return;
    }
    if (!validateJson(supplierJson)) return;
    setError("");
    setIsSubmitting(true);
    try {
      const { analysis_id } = await api.createAnalysis();
      await api.uploadDocuments(analysis_id, pdfFiles);
      await api.attachSupplier(analysis_id, JSON.parse(supplierJson));
      await api.runAnalysis(analysis_id);
      onAnalysisStarted(analysis_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start analysis.");
      setIsSubmitting(false);
    }
  };

  const parsedJson = (() => {
    try { return JSON.parse(supplierJson); } catch { return null; }
  })();

  return (
    <div className="min-h-screen bg-slate-100/60 flex items-center justify-center p-6">
      <div className="w-full max-w-2xl space-y-6 animate-fade-in">
        {/* Header with logo in a crisp light card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-8 shadow-sm text-center space-y-3">
          <div className="flex justify-center mb-1">
            <div className="relative h-14 w-48 sm:h-16 sm:w-56">
              <Image
                src="/logo.png"
                alt="BidBridge Logo"
                fill
                priority
                className="object-contain"
              />
            </div>
          </div>
          <div className="inline-flex items-center gap-1.5 bg-brand-50 text-brand-700 border border-brand-200/60 rounded-full px-3.5 py-1 text-xs font-semibold">
            <Zap className="h-3.5 w-3.5 text-brand-500 fill-brand-500" />
            AI Tender Qualification & Compliance Intelligence
          </div>
          <p className="text-slate-600 text-sm max-w-lg mx-auto">
            Upload tender RFP documentation and supplier profile JSON to receive an instant, auditable compliance decision.
          </p>
        </div>

        {/* PDF Upload */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-navy-900">
              <FileText className="h-4 w-4 text-brand-500" />
              Tender Documents
              <span className="ml-auto text-xs text-slate-400 font-normal">1–10 PDF files</span>
            </CardTitle>
            <CardDescription>Drag and drop your RFP, specifications, and annexes</CardDescription>
          </CardHeader>
          <CardContent>
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handlePdfDrop}
              onClick={() => pdfInputRef.current?.click()}
              className={cn(
                "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all",
                isDragging
                  ? "border-brand-500 bg-brand-50 scale-[1.01]"
                  : "border-slate-200 hover:border-brand-400 hover:bg-slate-50"
              )}
            >
              <Upload className={cn("h-8 w-8 mx-auto mb-3 transition-colors", isDragging ? "text-brand-500" : "text-slate-300")} />
              <p className="text-sm text-slate-700 font-medium">Drop PDF files here</p>
              <p className="text-xs text-slate-400 mt-1">or click to browse</p>
              <input ref={pdfInputRef} type="file" multiple accept=".pdf" className="hidden" onChange={handlePdfChange} />
            </div>

            {pdfFiles.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {pdfFiles.map((f, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm bg-slate-50 rounded-lg px-3 py-2 border border-slate-100">
                    <FileText className="h-3.5 w-3.5 text-brand-500 shrink-0" />
                    <span className="flex-1 truncate text-slate-700">{f.name}</span>
                    <span className="text-slate-400 text-xs shrink-0">{(f.size / 1024).toFixed(0)} KB</span>
                    <button onClick={(e) => { e.stopPropagation(); removeFile(i); }} className="text-slate-300 hover:text-red-500 transition-colors">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Supplier Profile */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-navy-900">
              <CheckCircle2 className="h-4 w-4 text-brand-500" />
              Supplier Profile
              {parsedJson && <span className="ml-2 text-xs text-emerald-600 font-normal">✓ {parsedJson.company_name || "Valid JSON"}</span>}
            </CardTitle>
            <CardDescription>Paste your company profile JSON or upload a .json file</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => jsonInputRef.current?.click()}>
                Upload JSON file
              </Button>
              <input ref={jsonInputRef} type="file" accept=".json" className="hidden" onChange={handleJsonFile} />
              <Button
                variant="ghost"
                size="sm"
                className="text-brand-600 hover:text-brand-700 hover:bg-brand-50 font-medium"
                onClick={() => {
                  const demo = `{"company_name":"CaspianTech LLC","founded_year":2018,"employees":42,"annual_revenue":{"2025":1200000,"currency":"AZN"},"certifications":[{"name":"ISO 9001","evidence_id":"EVD-001","issued_date":"2025-01-10","expiry_date":"2028-01-09"}],"projects":[{"name":"Network Modernization A","year":2025,"value":420000,"currency":"AZN","tags":["network infrastructure","enterprise"]}],"documents":[{"type":"certificate","name":"ISO 9001","evidence_id":"EVD-001"}],"complete_evidence_types":["CERTIFICATE"]}`;
                  setSupplierJson(demo);
                  validateJson(demo);
                }}
              >
                Load demo profile
              </Button>
            </div>
            <textarea
              value={supplierJson}
              onChange={(e) => { setSupplierJson(e.target.value); if (e.target.value) validateJson(e.target.value); }}
              placeholder='{"company_name": "Acme Corp", "certifications": [...], ...}'
              rows={6}
              className={cn(
                "w-full rounded-lg border px-3 py-2 text-xs font-mono text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none transition-colors",
                supplierError ? "border-red-300 bg-red-50" : "border-slate-200 bg-slate-50"
              )}
            />
            {supplierError && (
              <p className="flex items-center gap-1.5 text-xs text-red-600">
                <AlertCircle className="h-3 w-3" /> {supplierError}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Error & Submit */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            <AlertCircle className="h-4 w-4 shrink-0" /> {error}
          </div>
        )}

        <Button
          size="lg"
          className="w-full bg-navy-900 text-white hover:bg-navy-800 font-semibold shadow-md transition-all active:scale-[0.99]"
          onClick={handleSubmit}
          disabled={isSubmitting || pdfFiles.length === 0 || !supplierJson}
        >
          {isSubmitting ? (
            <><span className="animate-spin inline-block h-4 w-4 border-2 border-white/30 border-t-white rounded-full mr-2" />Starting Analysis...</>
          ) : (
            <><Zap className="h-4 w-4 text-cyan-500" />Run Compliance Analysis</>
          )}
        </Button>
      </div>
    </div>
  );
}
