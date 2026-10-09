"use client";

import { useState, useMemo } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown, Filter, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DrillDownModal } from "@/components/DrillDownModal";
import {
  STATUS_CONFIG,
  SEVERITY_CONFIG,
  MANDATORY_CONFIG,
  CATEGORY_LABELS,
  SEVERITY_ORDER,
  STATUS_ORDER,
  cn,
} from "@/lib/utils";
import type {
  Category,
  FilterState,
  MandatoryLevel,
  RequirementWithResult,
  Severity,
  SortDir,
  SortKey,
  Status,
} from "@/types";

const SEVERITY_VARIANT: Record<Severity, "critical" | "high" | "medium" | "low"> = {
  CRITICAL: "critical",
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
};

interface ComplianceMatrixProps {
  requirements: RequirementWithResult[];
}

export function ComplianceMatrix({ requirements }: ComplianceMatrixProps) {
  const [filters, setFilters] = useState<FilterState>({
    status: "ALL",
    category: "ALL",
    mandatory: "ALL",
    severity: "ALL",
  });
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("status");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selected, setSelected] = useState<RequirementWithResult | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const filtered = useMemo(() => {
    let out = requirements;
    if (filters.status !== "ALL") out = out.filter((r) => r.result.status === filters.status);
    if (filters.category !== "ALL") out = out.filter((r) => r.category === filters.category);
    if (filters.mandatory !== "ALL") out = out.filter((r) => r.mandatory_level === filters.mandatory);
    if (filters.severity !== "ALL")
      out = out.filter((r) => r.result.risk_severity === filters.severity);
    if (search) {
      const q = search.toLowerCase();
      out = out.filter(
        (r) =>
          r.text.toLowerCase().includes(q) ||
          r.requirement_id.toLowerCase().includes(q) ||
          CATEGORY_LABELS[r.category].toLowerCase().includes(q)
      );
    }
    return out;
  }, [requirements, filters, search]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let diff = 0;
      if (sortKey === "status") diff = STATUS_ORDER[a.result.status] - STATUS_ORDER[b.result.status];
      else if (sortKey === "category") diff = a.category.localeCompare(b.category);
      else if (sortKey === "mandatory_level") diff = a.mandatory_level.localeCompare(b.mandatory_level);
      else if (sortKey === "risk_severity") {
        const sa = a.result.risk_severity ? SEVERITY_ORDER[a.result.risk_severity] : 99;
        const sb = b.result.risk_severity ? SEVERITY_ORDER[b.result.risk_severity] : 99;
        diff = sa - sb;
      }
      return sortDir === "asc" ? diff : -diff;
    });
  }, [filtered, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return <ArrowUpDown className="h-3 w-3 text-slate-300" />;
    return sortDir === "asc"
      ? <ArrowUp className="h-3 w-3 text-brand-500" />
      : <ArrowDown className="h-3 w-3 text-brand-500" />;
  };

  const setFilter = <K extends keyof FilterState>(key: K, val: FilterState[K]) =>
    setFilters((f) => ({ ...f, [key]: val }));

  const activeFilterCount = Object.values(filters).filter((v) => v !== "ALL").length + (search ? 1 : 0);

  return (
    <div className="space-y-4">
      {/* Filter toolbar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-slate-400" />
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Filter Requirements</span>
          {activeFilterCount > 0 && (
            <span className="ml-auto text-xs text-brand-600 font-medium">{activeFilterCount} active</span>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {/* Search */}
          <div className="relative col-span-2 sm:col-span-1">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-slate-300" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              className="w-full h-8 pl-7 pr-3 text-xs border border-slate-200 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <Select value={filters.status} onValueChange={(v) => setFilter("status", v as Status | "ALL")}>
            <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All statuses</SelectItem>
              {(["MET", "PARTIALLY_MET", "NOT_MET", "UNKNOWN"] as Status[]).map((s) => (
                <SelectItem key={s} value={s}>{STATUS_CONFIG[s].label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filters.category} onValueChange={(v) => setFilter("category", v as Category | "ALL")}>
            <SelectTrigger><SelectValue placeholder="Category" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All categories</SelectItem>
              {(Object.keys(CATEGORY_LABELS) as Category[]).map((c) => (
                <SelectItem key={c} value={c}>{CATEGORY_LABELS[c]}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filters.mandatory} onValueChange={(v) => setFilter("mandatory", v as MandatoryLevel | "ALL")}>
            <SelectTrigger><SelectValue placeholder="Mandatory" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Any level</SelectItem>
              {(["MANDATORY", "PREFERRED", "INFORMATIONAL"] as MandatoryLevel[]).map((m) => (
                <SelectItem key={m} value={m}>{MANDATORY_CONFIG[m].label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filters.severity} onValueChange={(v) => setFilter("severity", v as Severity | "ALL")}>
            <SelectTrigger><SelectValue placeholder="Risk" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Any risk</SelectItem>
              {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as Severity[]).map((s) => (
                <SelectItem key={s} value={s}>{SEVERITY_CONFIG[s].label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {activeFilterCount > 0 && (
          <button
            onClick={() => { setFilters({ status: "ALL", category: "ALL", mandatory: "ALL", severity: "ALL" }); setSearch(""); }}
            className="text-xs text-slate-400 hover:text-slate-600 underline underline-offset-2"
          >
            Clear all filters
          </button>
        )}
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between text-xs text-slate-500 px-1">
        <span>Showing <strong className="text-slate-700">{sorted.length}</strong> of {requirements.length} requirements</span>
        <span className="text-slate-400">Click any row to see full details</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-slate-50">
              <TableHead className="w-[90px]">ID</TableHead>
              <TableHead>
                <button className="flex items-center gap-1 hover:text-slate-700" onClick={() => toggleSort("category")}>
                  Category <SortIcon col="category" />
                </button>
              </TableHead>
              <TableHead>
                <button className="flex items-center gap-1 hover:text-slate-700" onClick={() => toggleSort("mandatory_level")}>
                  Level <SortIcon col="mandatory_level" />
                </button>
              </TableHead>
              <TableHead>
                <button className="flex items-center gap-1 hover:text-slate-700" onClick={() => toggleSort("status")}>
                  Status <SortIcon col="status" />
                </button>
              </TableHead>
              <TableHead>
                <button className="flex items-center gap-1 hover:text-slate-700" onClick={() => toggleSort("risk_severity")}>
                  Risk <SortIcon col="risk_severity" />
                </button>
              </TableHead>
              <TableHead className="w-[40%]">Requirement</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10 text-slate-400">
                  No requirements match the current filters
                </TableCell>
              </TableRow>
            )}
            {sorted.map((req) => {
              const statusCfg = STATUS_CONFIG[req.result.status];
              const mandCfg = MANDATORY_CONFIG[req.mandatory_level];
              const sev = req.result.risk_severity;

              return (
                <TableRow
                  key={req.requirement_id}
                  onClick={() => { setSelected(req); setModalOpen(true); }}
                  className={cn(
                    req.result.risk_severity === "CRITICAL" && "bg-red-50/50",
                    req.result.risk_severity === "HIGH" && "bg-orange-50/30"
                  )}
                >
                  <TableCell>
                    <code className="text-xs text-slate-400 font-mono">{req.requirement_id}</code>
                  </TableCell>
                  <TableCell>
                    <span className="text-xs font-medium text-slate-600">{CATEGORY_LABELS[req.category]}</span>
                  </TableCell>
                  <TableCell>
                    <span className={cn("text-xs", mandCfg.classes)}>{mandCfg.label}</span>
                  </TableCell>
                  <TableCell>
                    <span className={cn("inline-flex items-center gap-1 text-xs font-medium", statusCfg.color)}>
                      <span className={cn("h-1.5 w-1.5 rounded-full", statusCfg.dot)} />
                      {statusCfg.label}
                    </span>
                  </TableCell>
                  <TableCell>
                    {sev ? (
                      <Badge variant={SEVERITY_VARIANT[sev]} className="text-xs">{sev}</Badge>
                    ) : (
                      <span className="text-slate-300 text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <p className="text-sm text-slate-700 line-clamp-2">{req.text}</p>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <DrillDownModal
        requirement={selected}
        open={modalOpen}
        onClose={() => { setModalOpen(false); setTimeout(() => setSelected(null), 300); }}
      />
    </div>
  );
}
